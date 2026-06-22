"""FastAPI application exposing normalized incident records."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from sentinel.models import IncidentRecord
from sentinel.pipeline import read
from sentinel.pipeline.store import create_tables


@asynccontextmanager
async def lifespan(_app: FastAPI):
    create_tables()
    yield


app = FastAPI(
    title="ai-sentinel-feed",
    description="Unified AI incident feed API",
    version="0.1.0",
    lifespan=lifespan,
)


class IncidentPage(BaseModel):
    items: list[IncidentRecord]
    total: int
    page: int
    page_size: int


class StatsResponse(BaseModel):
    by_vendor: list[dict] = Field(default_factory=list)
    by_technique: list[dict] = Field(default_factory=list)
    by_severity: list[dict] = Field(default_factory=list)
    over_time: list[dict] = Field(default_factory=list)


class TechniqueCount(BaseModel):
    technique: str
    count: int


@app.get("/")
def root() -> dict[str, str]:
    return {"status": "ok", "health": "/health"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/incidents", response_model=IncidentPage)
def list_incidents(
    source: str | None = None,
    vendor: str | None = None,
    severity: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> IncidentPage:
    items, total = read.list_incidents(
        source=source,
        vendor=vendor,
        severity=severity,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
    return IncidentPage(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@app.get("/incidents/stats", response_model=StatsResponse)
def incident_stats() -> StatsResponse:
    return StatsResponse(**read.incident_stats())


@app.get("/incidents/{incident_id}", response_model=IncidentRecord)
def get_incident(incident_id: str) -> IncidentRecord:
    record = read.get_incident(incident_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return record


@app.get("/feed", response_model=list[IncidentRecord])
def feed(limit: int = Query(50, ge=1, le=200)) -> list[IncidentRecord]:
    return read.get_feed(limit=limit)


@app.get("/atlas/techniques", response_model=list[TechniqueCount])
def atlas_techniques() -> list[TechniqueCount]:
    return [TechniqueCount(**item) for item in read.atlas_technique_counts()]
