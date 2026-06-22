"""Tests for FastAPI endpoints."""

from datetime import date, datetime, timezone

from fastapi.testclient import TestClient

from sentinel.api.main import app
from sentinel.models import IncidentRecord, Severity, Source

INGESTED_AT = datetime(2026, 6, 21, tzinfo=timezone.utc)

SAMPLE_RECORD = IncidentRecord.build(
    source=Source.AIAAIC,
    source_id="AIAAIC0001",
    title="Test incident",
    description="Example description",
    ingested_at=INGESTED_AT,
    incident_date=date(2024, 1, 1),
    vendor="Meta",
    severity=Severity.HIGH,
    atlas_technique="unmapped",
)


def test_list_incidents_endpoint(monkeypatch):
    monkeypatch.setattr(
        "sentinel.api.main.read.list_incidents",
        lambda **kwargs: ([SAMPLE_RECORD], 1),
    )
    client = TestClient(app)
    response = client.get("/incidents?page=1&page_size=10")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["source_id"] == "AIAAIC0001"


def test_get_incident_not_found(monkeypatch):
    monkeypatch.setattr("sentinel.api.main.read.get_incident", lambda incident_id: None)
    client = TestClient(app)
    response = client.get("/incidents/missing")
    assert response.status_code == 404


def test_feed_endpoint(monkeypatch):
    monkeypatch.setattr(
        "sentinel.api.main.read.get_feed",
        lambda limit=50: [SAMPLE_RECORD],
    )
    client = TestClient(app)
    response = client.get("/feed?limit=1")
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_stats_endpoint(monkeypatch):
    monkeypatch.setattr(
        "sentinel.api.main.read.incident_stats",
        lambda: {
            "by_vendor": [{"vendor": "Meta", "count": 1}],
            "by_technique": [],
            "by_severity": [{"severity": "high", "count": 1}],
            "over_time": [{"period": "2024-01", "count": 1}],
        },
    )
    client = TestClient(app)
    response = client.get("/incidents/stats")
    assert response.status_code == 200
    assert response.json()["by_vendor"][0]["vendor"] == "Meta"


def test_atlas_techniques_endpoint(monkeypatch):
    monkeypatch.setattr(
        "sentinel.api.main.read.atlas_technique_counts",
        lambda: [{"technique": "AML.T0051", "count": 3}],
    )
    client = TestClient(app)
    response = client.get("/atlas/techniques")
    assert response.status_code == 200
    assert response.json()[0]["technique"] == "AML.T0051"
