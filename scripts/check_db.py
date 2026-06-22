"""Verify PostgreSQL connectivity for ingest."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import text

from sentinel.config import DATABASE_URL
from sentinel.pipeline.store import create_tables, get_engine


def main() -> int:
    safe_url = DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL
    try:
        engine = get_engine()
        create_tables(engine)
        with engine.connect() as conn:
            total = conn.execute(text("SELECT COUNT(*) FROM incidents")).scalar_one()
        print(f"OK  postgres://...@{safe_url}  incidents={total}")
        return 0
    except Exception as exc:
        print(f"FAIL  postgres://...@{safe_url}  {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
