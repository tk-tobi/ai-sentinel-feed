"""Tests for JSONL export helpers."""

from datetime import date, datetime, timezone
from pathlib import Path

from sentinel.models import IncidentRecord, Severity, Source
from sentinel.pipeline.export import export_all, is_jailbreak_record, write_jsonl

INGESTED_AT = datetime(2026, 6, 21, tzinfo=timezone.utc)


def make_record(**overrides) -> IncidentRecord:
    data = {
        "source": Source.AIID,
        "source_id": "1",
        "title": "Routine incident",
        "description": "No special tags",
        "ingested_at": INGESTED_AT,
        "incident_date": date(2024, 5, 1),
        "severity": Severity.MEDIUM,
        "atlas_technique": "AML.T0051",
        "tags": [],
    }
    data.update(overrides)
    return IncidentRecord.build(**data)


def test_is_jailbreak_record_detects_tags_and_text():
    tagged = make_record(tags=["jailbreak"])
    textual = make_record(title="New jailbreak technique discovered")
    assert is_jailbreak_record(tagged)
    assert is_jailbreak_record(textual)
    assert not is_jailbreak_record(make_record())


def test_write_jsonl_writes_one_line_per_record(tmp_path: Path):
    records = [make_record(source_id="1"), make_record(source_id="2")]
    path = tmp_path / "incidents.jsonl"
    count = write_jsonl(path, records)
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert count == 2
    assert len(lines) == 2
    assert '"source_id": "1"' in lines[0]


def test_export_all_writes_expected_files(tmp_path: Path, monkeypatch):
    records = [
        make_record(source_id="1", atlas_technique="AML.T0051"),
        make_record(
            source_id="2",
            title="Prompt injection attack",
            atlas_technique="unmapped",
        ),
        make_record(source_id="3", atlas_technique="unmapped", tags=["other"]),
    ]
    monkeypatch.setattr(
        "sentinel.pipeline.export.list_all_incidents",
        lambda engine=None: records,
    )
    monkeypatch.setattr("sentinel.pipeline.export.EXPORTS_DIR", tmp_path)

    outputs = export_all(exports_dir=tmp_path)
    assert outputs["incidents"].exists()
    assert outputs["incidents_atlas_mapped"].read_text(encoding="utf-8").count("\n") == 1
    assert outputs["jailbreaks"].read_text(encoding="utf-8").count("\n") == 1
    assert any(path.name.startswith("manifest_") for path in tmp_path.iterdir())
