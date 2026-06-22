"""Print post-ingest summary stats for NOTES.md / verification."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import func, select

from sentinel.pipeline.read import incident_stats
from sentinel.pipeline.store import IncidentRow, get_engine


def main() -> None:
    engine = get_engine()
    with engine.connect() as conn:
        by_source = conn.execute(
            select(IncidentRow.source, func.count())
            .group_by(IncidentRow.source)
            .order_by(IncidentRow.source)
        ).all()

    print("=== Incident counts by source ===")
    total = 0
    for source, count in by_source:
        print(f"  {source}: {count}")
        total += count
    print(f"  TOTAL: {total}")
    print()

    stats = incident_stats(engine=engine)
    print("=== Top vendors ===")
    for row in stats["by_vendor"][:10]:
        print(f"  {row['vendor']}: {row['count']}")
    print()

    print("=== Top ATLAS techniques ===")
    for row in stats["by_technique"][:10]:
        print(f"  {row['technique']}: {row['count']}")
    print()

    print("=== Severity distribution ===")
    for row in stats["by_severity"]:
        print(f"  {row['severity']}: {row['count']}")
    print()

    print("=== JSON (copy to NOTES.md) ===")
    payload = {
        "total": total,
        "by_source": {source: count for source, count in by_source},
        "by_vendor": stats["by_vendor"][:10],
        "by_technique": stats["by_technique"][:10],
        "by_severity": stats["by_severity"],
    }
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
