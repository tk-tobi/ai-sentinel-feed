"""Tests for AIAAIC connector and ingest pipeline."""

from datetime import datetime, timezone

from sentinel.models import Source, make_incident_id
from sentinel.pipeline.deduplicate import deduplicate
from sentinel.pipeline.ingest import write_raw_snapshot
from sentinel.pipeline.normalize import normalize
from sentinel.sources.aiaaic import parse_csv_text

SAMPLE_CSV = """Incidents,,,,,
AIAAIC ID#,Headline,Occurred,Deployer,Developer,System name,Technology,Summary/links
,,,,,,,,
AIAAIC0001,Test headline,2024,Acme Corp,,Widget AI,Computer vision,https://example.com/a
AIAAIC0002,Another incident,2025,,Beta Inc,,LLM,
"""

INGESTED_AT = datetime(2026, 6, 21, 15, 0, tzinfo=timezone.utc)


def test_parse_csv_text_handles_header_rows():
    rows = parse_csv_text(SAMPLE_CSV)
    assert len(rows) == 2
    assert rows[0]["AIAAIC ID#"] == "AIAAIC0001"
    assert rows[0]["Deployer"] == "Acme Corp"
    assert rows[1]["Developer"] == "Beta Inc"


def test_deduplicate_keeps_latest_ingested_at():
    older = normalize(
        {"AIAAIC ID#": "AIAAIC0001", "Headline": "Old"},
        Source.AIAAIC,
        ingested_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    newer = normalize(
        {"AIAAIC ID#": "AIAAIC0001", "Headline": "New"},
        Source.AIAAIC,
        ingested_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
    )
    result = deduplicate([older, newer])
    assert len(result) == 1
    assert result[0].title == "New"


def test_write_raw_snapshot_appends_jsonl(tmp_path):
    records = [{"AIAAIC ID#": "AIAAIC0001", "Headline": "Test"}]
    path = write_raw_snapshot(
        "aiaaic",
        records,
        ingested_at=INGESTED_AT,
        raw_dir=tmp_path,
    )
    assert path.exists()
    assert path.name == "2026-06-21.jsonl"
    assert '"AIAAIC0001"' in path.read_text()


def test_ingest_source_dry_run(monkeypatch, tmp_path):
    from sentinel.pipeline import ingest as ingest_module

    monkeypatch.setattr(ingest_module, "RAW_DIR", tmp_path)
    monkeypatch.setitem(
        ingest_module.SOURCE_REGISTRY,
        "aiaaic",
        (Source.AIAAIC, lambda: parse_csv_text(SAMPLE_CSV)),
    )

    records = ingest_module.ingest_source(
        "aiaaic",
        ingested_at=INGESTED_AT,
        persist=False,
    )
    assert len(records) == 2
    assert records[0].source == Source.AIAAIC
    assert make_incident_id(Source.AIAAIC, "AIAAIC0001") == records[0].id
