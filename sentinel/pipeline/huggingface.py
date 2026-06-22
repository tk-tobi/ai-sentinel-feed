"""Publish normalized JSONL exports to HuggingFace Hub."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from sentinel.config import EXPORTS_DIR, HF_DATASET_REPO, HF_TOKEN
from sentinel.models import UNMAPPED_TECHNIQUE
from sentinel.pipeline.api_client import fetch_all_incidents
from sentinel.pipeline.export import export_all, is_jailbreak_record, write_jsonl

DATASET_CARD_PATH = Path(__file__).with_name("hf_dataset_card.md")


def dataset_card(
    *,
    repo_id: str,
    total_records: int,
    split_counts: dict[str, int],
    exported_at: str,
) -> str:
    """Render the HuggingFace dataset README from the template."""
    template = DATASET_CARD_PATH.read_text(encoding="utf-8")
    return (
        template.replace("{{repo_id}}", repo_id)
        .replace("{{total_records}}", str(total_records))
        .replace("{{exported_at}}", exported_at)
        .replace("{{split_counts}}", json.dumps(split_counts, indent=2))
    )


def publish_to_hub(
    export_paths: dict[str, Path],
    *,
    repo_id: str = HF_DATASET_REPO,
    token: str | None = HF_TOKEN,
    total_records: int | None = None,
) -> str | None:
    """Upload JSONL splits and dataset card to HuggingFace Hub."""
    if not token:
        print("[huggingface] skipped (HF_TOKEN not set)")
        return None
    if not repo_id:
        print("[huggingface] skipped (HF_DATASET_REPO not set)")
        return None

    from datasets import load_dataset
    from huggingface_hub import HfApi

    data_files = {name: str(path) for name, path in export_paths.items()}
    missing = [name for name, path in export_paths.items() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing export files: {', '.join(missing)}")

    exported_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    split_counts = {
        name: sum(1 for _ in path.open(encoding="utf-8"))
        for name, path in export_paths.items()
    }
    total = total_records if total_records is not None else split_counts.get("incidents", 0)

    api = HfApi()
    api.create_repo(repo_id=repo_id, repo_type="dataset", exist_ok=True, token=token)

    card = dataset_card(
        repo_id=repo_id,
        total_records=total,
        split_counts=split_counts,
        exported_at=exported_at,
    )
    api.upload_file(
        path_or_fileobj=card.encode("utf-8"),
        path_in_repo="README.md",
        repo_id=repo_id,
        repo_type="dataset",
        token=token,
        commit_message=f"Update dataset card ({total} incidents)",
    )

    dataset = load_dataset("json", data_files=data_files)
    dataset.push_to_hub(
        repo_id,
        token=token,
        commit_message=f"Sync exports ({total} incidents)",
    )
    print(f"[huggingface] published {repo_id} splits={list(export_paths)}")
    return repo_id


def export_and_publish(
    *,
    exports_dir: Path = EXPORTS_DIR,
    repo_id: str = HF_DATASET_REPO,
    token: str | None = HF_TOKEN,
    engine=None,
) -> str | None:
    """Export from PostgreSQL and publish to HuggingFace Hub."""
    paths = export_all(exports_dir=exports_dir, engine=engine)
    return publish_to_hub(paths, repo_id=repo_id, token=token)


def publish_from_api(
    api_url: str,
    *,
    exports_dir: Path = EXPORTS_DIR,
    repo_id: str = HF_DATASET_REPO,
    token: str | None = HF_TOKEN,
) -> str | None:
    """Fetch incidents from the public API, write exports, and publish."""
    records = fetch_all_incidents(api_url)
    outputs = {
        "incidents": exports_dir / "incidents.jsonl",
        "incidents_atlas_mapped": exports_dir / "incidents_atlas_mapped.jsonl",
        "jailbreaks": exports_dir / "jailbreaks.jsonl",
    }
    write_jsonl(outputs["incidents"], records)
    write_jsonl(
        outputs["incidents_atlas_mapped"],
        [record for record in records if record.atlas_technique != UNMAPPED_TECHNIQUE],
    )
    write_jsonl(
        outputs["jailbreaks"],
        [record for record in records if is_jailbreak_record(record)],
    )
    return publish_to_hub(outputs, repo_id=repo_id, token=token, total_records=len(records))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Publish incident exports to HuggingFace Hub")
    parser.add_argument(
        "--api-url",
        help="Fetch incidents from the public API instead of PostgreSQL",
    )
    parser.add_argument(
        "--repo-id",
        default=HF_DATASET_REPO,
        help="HuggingFace dataset repo id (default: HF_DATASET_REPO env)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Export only; do not upload to HuggingFace Hub",
    )
    args = parser.parse_args(argv)

    if args.dry_run:
        if args.api_url:
            records = fetch_all_incidents(args.api_url)
            print(f"[huggingface] dry run: fetched {len(records)} incidents from API")
        else:
            paths = export_all()
            for name, path in paths.items():
                print(f"[huggingface] dry run: exported {name} -> {path}")
        return

    if args.api_url:
        publish_from_api(args.api_url, repo_id=args.repo_id)
        return

    export_and_publish(repo_id=args.repo_id)


if __name__ == "__main__":
    main()
