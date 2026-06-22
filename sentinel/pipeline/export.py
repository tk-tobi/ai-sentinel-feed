"""JSONL export helpers for normalized incident records."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from sentinel.config import EXPORTS_DIR
from sentinel.models import IncidentRecord, UNMAPPED_TECHNIQUE
from sentinel.pipeline.read import list_all_incidents

JAILBREAK_TERMS = ("jailbreak", "prompt-injection", "prompt injection")


def record_to_json(record: IncidentRecord) -> dict:
    payload = record.model_dump(mode="json")
    payload["source"] = record.source.value
    payload["severity"] = record.severity.value
    return payload


def is_jailbreak_record(record: IncidentRecord) -> bool:
    haystack = " ".join(
        [
            record.title,
            record.description,
            " ".join(record.tags),
        ]
    ).lower()
    return any(term in haystack for term in JAILBREAK_TERMS)


def write_jsonl(path: Path, records: list[IncidentRecord]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record_to_json(record), default=str))
            handle.write("\n")
    return len(records)


def export_all(
    *,
    exports_dir: Path = EXPORTS_DIR,
    engine=None,
) -> dict[str, Path]:
    """Write README export files and return output paths."""
    records = list_all_incidents(engine=engine)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

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

    manifest = exports_dir / f"manifest_{timestamp}.json"
    manifest.write_text(
        json.dumps(
            {
                "exported_at": timestamp,
                "total_records": len(records),
                "files": {key: str(path.name) for key, path in outputs.items()},
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    return outputs


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Export normalized incidents to JSONL")
    parser.add_argument(
        "--hub",
        action="store_true",
        help="Publish exports to HuggingFace Hub after writing files",
    )
    args = parser.parse_args()

    outputs = export_all()
    for name, path in outputs.items():
        print(f"exported {name} -> {path}")

    if args.hub:
        from sentinel.pipeline.huggingface import publish_to_hub

        publish_to_hub(outputs)


if __name__ == "__main__":
    main()
