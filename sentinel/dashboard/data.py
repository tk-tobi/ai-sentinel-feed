"""Load incident data for the dashboard (PostgreSQL locally, HTTP API in production)."""

from __future__ import annotations

import os
from typing import Any

import httpx
import streamlit as st

from sentinel.models import IncidentRecord

API_PAGE_SIZE = 200
SECRET_KEYS = ("SENTINEL_API_URL", "API_URL")


def resolve_api_url() -> str | None:
    """Return the public API base URL from Streamlit secrets or environment."""
    for key in SECRET_KEYS:
        try:
            if key in st.secrets:
                return str(st.secrets[key]).strip().rstrip("/")
        except (FileNotFoundError, AttributeError, TypeError):
            pass

    for key in SECRET_KEYS:
        value = os.getenv(key)
        if value:
            return value.strip().rstrip("/")
    return None


def fetch_incidents_from_api(base_url: str) -> list[IncidentRecord]:
    """Page through GET /incidents until all records are loaded."""
    records: list[IncidentRecord] = []
    page = 1

    with httpx.Client(timeout=120.0) as client:
        while True:
            response = client.get(
                f"{base_url}/incidents",
                params={"page": page, "page_size": API_PAGE_SIZE},
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


def load_incidents() -> list[IncidentRecord]:
    """Load incidents from the API when configured, otherwise from PostgreSQL."""
    api_url = resolve_api_url()
    if api_url:
        return fetch_incidents_from_api(api_url)

    from sentinel.pipeline import read

    return read.list_all_incidents()
