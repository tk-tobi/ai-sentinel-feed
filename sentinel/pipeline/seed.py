"""Seed PostgreSQL from bundled JSONL when the database is empty."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sentinel.config import PROJECT_ROOT
from sentinel.models import IncidentRecord
from sentinel.pipeline.store import count_incidents, create_tables, upsert_incidents

DEFAULT_SEED_PATH = PROJECT_ROOT / "docker" / "seed" / "incidents.jsonl"


def load_records_from_jsonl(path: Path) -> list[IncidentRecord]:
    records: list[IncidentRecord] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            records.append(IncidentRecord.model_validate(json.loads(line)))
    return records


def seed_database(
    path: Path = DEFAULT_SEED_PATH,
    *,
    force: bool = False,
    engine=None,
) -> int:
    """Load seed file if the incidents table is empty. Returns rows written."""
    create_tables(engine)
    existing = count_incidents(engine=engine)
    if existing and not force:
        print(f"[seed] skipped, database already has {existing} incidents")
        return 0

    if not path.exists():
        raise FileNotFoundError(f"Seed file not found: {path}")

    records = load_records_from_jsonl(path)
    if not records:
        print(f"[seed] seed file is empty: {path}")
        return 0

    written = upsert_incidents(records, engine=engine)
    print(f"[seed] loaded {written} incidents from {path}")
    return written


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Seed PostgreSQL from JSONL")
    parser.add_argument(
        "--seed-file",
        type=Path,
        default=DEFAULT_SEED_PATH,
        help="Path to incidents JSONL seed file",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Load seed even if incidents already exist",
    )
    args = parser.parse_args(argv)
    seed_database(args.seed_file, force=args.force)


if __name__ == "__main__":
    main()
