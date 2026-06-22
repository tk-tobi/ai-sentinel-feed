"""Tests for database seeding from JSONL."""

import json
from datetime import datetime, timezone

from sentinel.models import IncidentRecord, Severity, Source
from sentinel.pipeline.seed import load_records_from_jsonl, seed_database

INGESTED_AT = datetime(2026, 6, 22, 12, 0, tzinfo=timezone.utc)


def test_load_records_from_jsonl(tmp_path):
    record = IncidentRecord.build(
        source=Source.AIAAIC,
        source_id="AIAAIC0001",
        title="Test",
        description="Example",
        ingested_at=INGESTED_AT,
        severity=Severity.LOW,
    )
    path = tmp_path / "seed.jsonl"
    path.write_text(json.dumps(record.model_dump(mode="json")) + "\n", encoding="utf-8")

    loaded = load_records_from_jsonl(path)
    assert len(loaded) == 1
    assert loaded[0].source_id == "AIAAIC0001"


def test_seed_database_skips_when_populated(monkeypatch, tmp_path):
    record = IncidentRecord.build(
        source=Source.NVD,
        source_id="CVE-TEST-1",
        title="CVE",
        description="desc",
        ingested_at=INGESTED_AT,
    )
    path = tmp_path / "seed.jsonl"
    path.write_text(json.dumps(record.model_dump(mode="json")) + "\n", encoding="utf-8")

    monkeypatch.setattr("sentinel.pipeline.seed.count_incidents", lambda **_: 5)
    monkeypatch.setattr("sentinel.pipeline.seed.upsert_incidents", lambda *a, **k: 0)

    assert seed_database(path) == 0
