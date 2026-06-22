"""Persist normalized incident records to PostgreSQL."""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, DateTime, String, Text, create_engine, text
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from sentinel.config import DATABASE_URL
from sentinel.models import IncidentRecord

UPSERT_BATCH_SIZE = 200


def sanitize_json_value(value: Any) -> Any:
    """Make values safe for PostgreSQL JSONB (NaN/Inf are rejected)."""
    if isinstance(value, dict):
        return {str(key): sanitize_json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_json_value(item) for item in value]
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


class Base(DeclarativeBase):
    pass


class IncidentRow(Base):
    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source: Mapped[str] = mapped_column(String(32), index=True)
    source_id: Mapped[str] = mapped_column(String(128), index=True)
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    incident_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    vendor: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    system: Mapped[str | None] = mapped_column(Text, nullable=True)
    atlas_technique: Mapped[str] = mapped_column(String(32), index=True)
    atlas_tactic: Mapped[str | None] = mapped_column(String(128), nullable=True)
    severity: Mapped[str] = mapped_column(String(32), index=True)
    tags: Mapped[list] = mapped_column(JSONB)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw: Mapped[dict] = mapped_column(JSONB)


def get_engine(database_url: str = DATABASE_URL):
    return create_engine(database_url, future=True)


def create_tables(engine=None) -> None:
    engine = engine or get_engine()
    Base.metadata.create_all(engine)
    _upgrade_columns(engine)


def _upgrade_columns(engine) -> None:
    """Widen columns when an older schema already exists (idempotent)."""
    alters = (
        "ALTER TABLE incidents ALTER COLUMN vendor TYPE TEXT",
        "ALTER TABLE incidents ALTER COLUMN system TYPE TEXT",
    )
    with engine.begin() as conn:
        for stmt in alters:
            conn.execute(text(stmt))


def _record_to_row(record: IncidentRecord) -> dict:
    return {
        "id": record.id,
        "source": record.source.value,
        "source_id": record.source_id,
        "title": record.title,
        "description": record.description,
        "incident_date": record.incident_date,
        "ingested_at": record.ingested_at,
        "vendor": record.vendor,
        "system": record.system,
        "atlas_technique": record.atlas_technique,
        "atlas_tactic": record.atlas_tactic,
        "severity": record.severity.value,
        "tags": record.tags,
        "url": record.url,
        "raw": sanitize_json_value(record.raw),
    }


def _upsert_rows(session: Session, rows: list[dict]) -> None:
    stmt = insert(IncidentRow).values(rows)
    update_columns = {
        column.name: stmt.excluded[column.name]
        for column in IncidentRow.__table__.columns
        if column.name != "id"
    }
    upsert = stmt.on_conflict_do_update(index_elements=["id"], set_=update_columns)
    session.execute(upsert)


def upsert_incidents(
    records: list[IncidentRecord],
    *,
    engine=None,
) -> int:
    """Insert or update incidents by primary key. Returns rows written."""
    if not records:
        return 0

    engine = engine or get_engine()
    create_tables(engine)

    rows = [_record_to_row(record) for record in records]

    with Session(engine) as session:
        for offset in range(0, len(rows), UPSERT_BATCH_SIZE):
            batch = rows[offset : offset + UPSERT_BATCH_SIZE]
            _upsert_rows(session, batch)
        session.commit()
    return len(rows)


def count_incidents(*, engine=None) -> int:
    engine = engine or get_engine()
    with engine.connect() as conn:
        return conn.execute(text("SELECT COUNT(*) FROM incidents")).scalar_one()
