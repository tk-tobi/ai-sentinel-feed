"""Ingestion orchestrator, fetch, snapshot raw data, normalize, store."""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sentinel.config import RAW_DIR
from sentinel.models import IncidentRecord, Source
from sentinel.pipeline.deduplicate import deduplicate
from sentinel.pipeline.normalize import normalize
from sentinel.pipeline.store import count_incidents, upsert_incidents
from sentinel.sources import aiid, aiaaic, nvd

FetchFn = Callable[[], list[dict[str, Any]]]

SOURCE_REGISTRY: dict[str, tuple[Source, FetchFn]] = {
    "aiaaic": (Source.AIAAIC, aiaaic.fetch),
    "aiid": (Source.AIID, aiid.fetch),
    "nvd": (Source.NVD, nvd.fetch),
}


def write_raw_snapshot(
    source: str,
    records: list[dict[str, Any]],
    *,
    ingested_at: datetime,
    raw_dir: Path = RAW_DIR,
) -> Path:
    """Write untouched source payloads to data/raw/{source}/YYYY-MM-DD.jsonl."""
    day = ingested_at.date().isoformat()
    output_dir = raw_dir / source
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{day}.jsonl"

    with output_path.open("a", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, default=str))
            handle.write("\n")

    return output_path


def ingest_source(
    source_name: str,
    *,
    ingested_at: datetime | None = None,
    persist: bool = True,
) -> list[IncidentRecord]:
    """Run the full ingest pipeline for a single source."""
    if source_name not in SOURCE_REGISTRY:
        supported = ", ".join(sorted(SOURCE_REGISTRY))
        raise ValueError(f"Unknown source {source_name!r}. Supported: {supported}")

    source, fetch_fn = SOURCE_REGISTRY[source_name]
    ingested_at = ingested_at or datetime.now(timezone.utc)

    raw_records = fetch_fn()
    snapshot_path = write_raw_snapshot(source_name, raw_records, ingested_at=ingested_at)

    normalized = [
        normalize(raw, source, ingested_at=ingested_at)
        for raw in raw_records
    ]
    records = deduplicate(normalized)

    if persist:
        written = upsert_incidents(records)
        total = count_incidents()
        print(
            f"[{source_name}] fetched={len(raw_records)} "
            f"normalized={len(records)} upserted={written} "
            f"db_total={total} raw={snapshot_path}"
        )
    else:
        print(
            f"[{source_name}] fetched={len(raw_records)} "
            f"normalized={len(records)} raw={snapshot_path} (dry run)"
        )

    return records


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Ingest incidents from a data source")
    parser.add_argument(
        "--source",
        required=True,
        choices=[*sorted(SOURCE_REGISTRY), "all"],
        help="Source connector to run, or 'all' for every registered source",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and normalize without writing to PostgreSQL",
    )
    args = parser.parse_args(argv)

    sources = sorted(SOURCE_REGISTRY) if args.source == "all" else [args.source]
    for source_name in sources:
        ingest_source(source_name, persist=not args.dry_run)

    if not args.dry_run and args.source == "all":
        from sentinel.pipeline.export import export_all
        from sentinel.pipeline.huggingface import publish_to_hub

        export_paths = export_all()
        publish_to_hub(export_paths)


if __name__ == "__main__":
    main()
