"""Read/query helpers for normalized incidents in PostgreSQL."""

from __future__ import annotations

from datetime import date

from sqlalchemy import Date, cast, func, select
from sqlalchemy.orm import Session

from sentinel.models import IncidentRecord, Severity, Source, UNMAPPED_TECHNIQUE
from sentinel.pipeline.store import IncidentRow, get_engine


def row_to_record(row: IncidentRow) -> IncidentRecord:
    return IncidentRecord(
        id=row.id,
        source=Source(row.source),
        source_id=row.source_id,
        title=row.title,
        description=row.description,
        incident_date=row.incident_date,
        ingested_at=row.ingested_at,
        vendor=row.vendor,
        system=row.system,
        atlas_technique=row.atlas_technique,
        atlas_tactic=row.atlas_tactic,
        severity=Severity(row.severity),
        tags=row.tags or [],
        url=row.url,
        raw=row.raw or {},
    )


def _apply_filters(
    stmt,
    *,
    source: str | None = None,
    vendor: str | None = None,
    severity: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
):
    if source:
        stmt = stmt.where(IncidentRow.source == source)
    if vendor:
        stmt = stmt.where(IncidentRow.vendor.ilike(f"%{vendor}%"))
    if severity:
        stmt = stmt.where(IncidentRow.severity == severity)
    if date_from:
        stmt = stmt.where(IncidentRow.incident_date >= date_from)
    if date_to:
        stmt = stmt.where(IncidentRow.incident_date <= date_to)
    return stmt


def list_incidents(
    *,
    source: str | None = None,
    vendor: str | None = None,
    severity: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = 1,
    page_size: int = 50,
    engine=None,
) -> tuple[list[IncidentRecord], int]:
    engine = engine or get_engine()
    page = max(page, 1)
    page_size = min(max(page_size, 1), 200)
    offset = (page - 1) * page_size

    base = select(IncidentRow)
    base = _apply_filters(
        base,
        source=source,
        vendor=vendor,
        severity=severity,
        date_from=date_from,
        date_to=date_to,
    )

    with Session(engine) as session:
        total = session.scalar(select(func.count()).select_from(base.subquery())) or 0
        rows = session.scalars(
            base.order_by(IncidentRow.ingested_at.desc())
            .offset(offset)
            .limit(page_size)
        ).all()

    return [row_to_record(row) for row in rows], total


def get_incident(incident_id: str, *, engine=None) -> IncidentRecord | None:
    engine = engine or get_engine()
    with Session(engine) as session:
        row = session.get(IncidentRow, incident_id)
    return row_to_record(row) if row else None


def get_feed(*, limit: int = 50, engine=None) -> list[IncidentRecord]:
    engine = engine or get_engine()
    limit = min(max(limit, 1), 200)
    with Session(engine) as session:
        rows = session.scalars(
            select(IncidentRow)
            .order_by(IncidentRow.ingested_at.desc())
            .limit(limit)
        ).all()
    return [row_to_record(row) for row in rows]


def list_all_incidents(*, engine=None) -> list[IncidentRecord]:
    engine = engine or get_engine()
    with Session(engine) as session:
        rows = session.scalars(
            select(IncidentRow).order_by(IncidentRow.ingested_at.desc())
        ).all()
    return [row_to_record(row) for row in rows]


def incident_stats(*, engine=None) -> dict:
    engine = engine or get_engine()
    period = func.to_char(
        func.coalesce(IncidentRow.incident_date, cast(IncidentRow.ingested_at, Date)),
        "YYYY-MM",
    ).label("period")

    with Session(engine) as session:
        by_vendor = session.execute(
            select(IncidentRow.vendor, func.count())
            .where(IncidentRow.vendor.is_not(None))
            .group_by(IncidentRow.vendor)
            .order_by(func.count().desc())
            .limit(20)
        ).all()
        by_technique = session.execute(
            select(IncidentRow.atlas_technique, func.count())
            .group_by(IncidentRow.atlas_technique)
            .order_by(func.count().desc())
            .limit(20)
        ).all()
        by_severity = session.execute(
            select(IncidentRow.severity, func.count())
            .group_by(IncidentRow.severity)
            .order_by(func.count().desc())
        ).all()
        over_time = session.execute(
            select(period, func.count())
            .group_by(period)
            .order_by(period)
        ).all()

    return {
        "by_vendor": [
            {"vendor": vendor, "count": count} for vendor, count in by_vendor if vendor
        ],
        "by_technique": [
            {"technique": technique, "count": count}
            for technique, count in by_technique
        ],
        "by_severity": [
            {"severity": severity, "count": count}
            for severity, count in by_severity
        ],
        "over_time": [
            {"period": period, "count": count}
            for period, count in over_time
            if period
        ],
    }


def atlas_technique_counts(*, engine=None) -> list[dict]:
    engine = engine or get_engine()
    with Session(engine) as session:
        rows = session.execute(
            select(IncidentRow.atlas_technique, func.count())
            .where(IncidentRow.atlas_technique != UNMAPPED_TECHNIQUE)
            .group_by(IncidentRow.atlas_technique)
            .order_by(func.count().desc())
        ).all()

    return [
        {"technique": technique, "count": count}
        for technique, count in rows
    ]
