"""Load incident data for the dashboard (PostgreSQL locally, HTTP API in production)."""

from __future__ import annotations

import os

import streamlit as st

from sentinel.models import IncidentRecord
from sentinel.pipeline.api_client import fetch_all_incidents

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


def load_incidents() -> list[IncidentRecord]:
    """Load incidents from the API when configured, otherwise from PostgreSQL."""
    api_url = resolve_api_url()
    if api_url:
        return fetch_all_incidents(api_url)

    from sentinel.pipeline import read

    return read.list_all_incidents()
