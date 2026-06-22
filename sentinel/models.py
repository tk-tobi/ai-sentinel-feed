"""Shared data models for normalized incident records."""

from __future__ import annotations

import hashlib
from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

UNMAPPED_TECHNIQUE = "unmapped"


class Source(str, Enum):
    NVD = "NVD"
    AIID = "AIID"
    AIAAIC = "AIAAIC"
    ATLAS = "ATLAS"
    GITHUB = "GitHub"


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


def make_incident_id(source: str | Source, source_id: str) -> str:
    """Stable SHA-256 id from source namespace + upstream identifier."""
    key = f"{source}{source_id}"
    return hashlib.sha256(key.encode()).hexdigest()


class IncidentRecord(BaseModel):
    id: str
    source: Source
    source_id: str
    title: str
    description: str
    incident_date: date | None = None
    ingested_at: datetime
    vendor: str | None = None
    system: str | None = None
    atlas_technique: str = UNMAPPED_TECHNIQUE
    atlas_tactic: str | None = None
    severity: Severity = Severity.INFORMATIONAL
    tags: list[str] = Field(default_factory=list)
    url: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def build(
        cls,
        *,
        source: Source,
        source_id: str,
        title: str,
        description: str,
        ingested_at: datetime,
        incident_date: date | None = None,
        vendor: str | None = None,
        system: str | None = None,
        atlas_technique: str = UNMAPPED_TECHNIQUE,
        atlas_tactic: str | None = None,
        severity: Severity = Severity.INFORMATIONAL,
        tags: list[str] | None = None,
        url: str | None = None,
        raw: dict[str, Any] | None = None,
    ) -> IncidentRecord:
        return cls(
            id=make_incident_id(source, source_id),
            source=source,
            source_id=source_id,
            title=title,
            description=description,
            incident_date=incident_date,
            ingested_at=ingested_at,
            vendor=vendor,
            system=system,
            atlas_technique=atlas_technique,
            atlas_tactic=atlas_tactic,
            severity=severity,
            tags=tags or [],
            url=url,
            raw=raw or {},
        )
