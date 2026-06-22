"""Re-apply ATLAS mapping to incidents already stored in PostgreSQL."""

from __future__ import annotations

import argparse

from sentinel.pipeline.atlas_map import apply_atlas_mapping
from sentinel.pipeline.read import list_all_incidents
from sentinel.pipeline.store import count_incidents, upsert_incidents
from sentinel.sources.atlas import load_atlas


def remap_stored_incidents(*, engine=None) -> tuple[int, int]:
    """Update atlas_technique/atlas_tactic for all rows. Returns (total, mapped)."""
    atlas = load_atlas()
    records = list_all_incidents(engine=engine)
    remapped = [apply_atlas_mapping(record, atlas) for record in records]
    upsert_incidents(remapped, engine=engine)

    mapped = sum(1 for record in remapped if record.atlas_technique != "unmapped")
    return len(remapped), mapped


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Re-apply ATLAS heuristic mapping to stored incidents"
    )
    parser.parse_args(argv)

    total, mapped = remap_stored_incidents()
    db_total = count_incidents()
    print(
        f"[remap_atlas] updated={total} mapped={mapped} "
        f"unmapped={total - mapped} db_total={db_total}"
    )


if __name__ == "__main__":
    main()
