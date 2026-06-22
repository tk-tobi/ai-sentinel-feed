"""Deduplicate normalized incident records by stable id."""

from __future__ import annotations

from sentinel.models import IncidentRecord


def deduplicate(records: list[IncidentRecord]) -> list[IncidentRecord]:
    """Keep one record per id, preferring the latest ingested_at timestamp."""
    by_id: dict[str, IncidentRecord] = {}
    for record in records:
        existing = by_id.get(record.id)
        if existing is None or record.ingested_at >= existing.ingested_at:
            by_id[record.id] = record
    return list(by_id.values())
