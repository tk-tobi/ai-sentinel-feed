"""HTTP client for the read-only incident API."""

from __future__ import annotations

from typing import Any

import httpx

from sentinel.models import IncidentRecord

DEFAULT_PAGE_SIZE = 200


def fetch_all_incidents(base_url: str, *, page_size: int = DEFAULT_PAGE_SIZE) -> list[IncidentRecord]:
    """Page through GET /incidents until all records are loaded."""
    records: list[IncidentRecord] = []
    page = 1
    base_url = base_url.strip().rstrip("/")

    with httpx.Client(timeout=120.0) as client:
        while True:
            response = client.get(
                f"{base_url}/incidents",
                params={"page": page, "page_size": page_size},
            )
            response.raise_for_status()
            payload: dict[str, Any] = response.json()
            batch = payload.get("items", [])
            total = int(payload.get("total", 0))

            for item in batch:
                records.append(IncidentRecord.model_validate(item))

            if not batch or len(records) >= total:
                break
            page += 1

    return records
