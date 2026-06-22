"""AIAAIC source connector — Google Sheets CSV export."""

from __future__ import annotations

from io import StringIO
from typing import Any

import httpx
import pandas as pd

from sentinel.config import AIAAIC_CSV_URL

DEFAULT_TIMEOUT = 60.0


def parse_csv_text(csv_text: str) -> list[dict[str, Any]]:
    """Parse AIAAIC CSV export into row dicts.

    The sheet uses a non-standard header layout:
      row 0 — merged title row (skipped)
      row 1 — column names (header)
      row 2 — sub-header row (skipped)
      row 3+ — data
    """
    frame = pd.read_csv(StringIO(csv_text), header=1, skiprows=[2])
    frame = frame.where(pd.notnull(frame), None)
    return frame.to_dict(orient="records")


def fetch(csv_url: str = AIAAIC_CSV_URL, *, timeout: float = DEFAULT_TIMEOUT) -> list[dict[str, Any]]:
    """Download and parse the AIAAIC incidents spreadsheet."""
    response = httpx.get(csv_url, follow_redirects=True, timeout=timeout)
    response.raise_for_status()
    return parse_csv_text(response.text)
