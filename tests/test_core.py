"""Tests for core models, ATLAS loader, and normalization."""

from datetime import date, datetime, timezone

import pytest

from sentinel.models import Severity, Source, make_incident_id
from sentinel.pipeline.normalize import mask_pii, normalize
from sentinel.pipeline.store import sanitize_json_value
from sentinel.severity import cvss_to_severity, qualitative_harm_to_severity
from sentinel.sources.atlas import AtlasTaxonomy, DEFAULT_ATLAS_PATH

INGESTED_AT = datetime(2026, 6, 21, 12, 0, tzinfo=timezone.utc)


def test_make_incident_id_is_stable():
    first = make_incident_id(Source.NVD, "CVE-2021-43811")
    second = make_incident_id("NVD", "CVE-2021-43811")
    assert first == second
    assert len(first) == 64


def test_cvss_to_severity_buckets():
    assert cvss_to_severity(9.8) == Severity.CRITICAL
    assert cvss_to_severity(7.8) == Severity.HIGH
    assert cvss_to_severity(5.5) == Severity.MEDIUM
    assert cvss_to_severity(2.1) == Severity.LOW
    assert cvss_to_severity(None) == Severity.INFORMATIONAL


def test_mask_pii_redacts_common_patterns():
    text = "Contact alice@example.com or 555-123-4567 or 123-45-6789"
    masked = mask_pii(text)
    assert "alice@example.com" not in masked
    assert "555-123-4567" not in masked
    assert "123-45-6789" not in masked


@pytest.mark.skipif(
    not DEFAULT_ATLAS_PATH.exists(),
    reason="ATLAS YAML not downloaded locally",
)
def test_atlas_taxonomy_loads_techniques():
    atlas = AtlasTaxonomy.from_yaml()
    assert len(atlas.list_techniques()) > 100
    technique = atlas.get_technique("AML.T0000")
    assert technique is not None
    assert technique.name == "Search Open Technical Databases"
    assert technique.tactic_names[0] == "Reconnaissance"


def test_normalize_nvd_sample_shape():
    raw = {
        "search_keyword": "pytorch",
        "cve": {
            "id": "CVE-2021-43811",
            "published": "2021-12-08T23:15:08.123",
            "descriptions": [
                {
                    "lang": "en",
                    "value": "PyTorch-related unsafe YAML loading vulnerability.",
                }
            ],
            "affected": [
                {
                    "affectedData": [
                        {"vendor": "awslabs", "product": "sockeye"}
                    ]
                }
            ],
            "metrics": {
                "cvssMetricV31": [
                    {
                        "cvssData": {
                            "baseScore": 7.8,
                            "baseSeverity": "HIGH",
                        }
                    }
                ]
            },
            "weaknesses": [
                {"description": [{"lang": "en", "value": "CWE-94"}]}
            ],
        }
    }
    record = normalize(raw, Source.NVD, ingested_at=INGESTED_AT)
    assert record.source == Source.NVD
    assert record.source_id == "CVE-2021-43811"
    assert record.severity == Severity.HIGH
    assert record.vendor == "awslabs"
    assert record.incident_date == date(2021, 12, 8)
    assert "CWE-94" in record.tags
    assert "pytorch" in record.tags


def test_normalize_aiid_sample_shape():
    raw = {
        "incident_id": 1,
        "title": "Google's YouTube Kids App Presents Inappropriate Content",
        "description": "Filtering algorithms exposed children to disturbing videos.",
        "date": "2015-05-19",
        "AllegedDeployerOfAISystem": [{"name": "YouTube"}],
        "reports": [{"report_number": 15, "title": "BBC report"}],
    }
    record = normalize(raw, Source.AIID, ingested_at=INGESTED_AT)
    assert record.source == Source.AIID
    assert record.source_id == "1"
    assert record.vendor == "YouTube"
    assert record.severity == qualitative_harm_to_severity(raw["description"])
    assert record.raw["reports"][0]["report_number"] == 15


def test_sanitize_json_value_replaces_nan():
    assert sanitize_json_value({"Deployer": float("nan"), "ok": 1}) == {
        "Deployer": None,
        "ok": 1,
    }


def test_qualitative_harm_to_severity_coerces_non_string_values():
    assert qualitative_harm_to_severity("privacy harm", float("nan")) == Severity.HIGH
    assert qualitative_harm_to_severity(None, float("nan")) == Severity.INFORMATIONAL


def test_normalize_aiaaic_sample_shape():
    raw = {
        "AIAAIC ID#": "AIAAIC2264",
        "Headline": "Meta captures employee mouse movements to train AI models",
        "Occurred": "2026",
        "Deployer": None,
        "Developer": "Meta",
        "System name": None,
        "Technology": "Workplace monitoring",
        "Ethical issue (taxonomy)": "Surveillance",
        "Summary/links": "https://example.com/story",
    }
    record = normalize(raw, Source.AIAAIC, ingested_at=INGESTED_AT)
    assert record.source == Source.AIAAIC
    assert record.source_id == "AIAAIC2264"
    assert record.vendor == "Meta"
    assert record.system == "Workplace monitoring"
    assert record.incident_date == date(2026, 1, 1)
    assert record.url == "https://example.com/story"


def test_normalize_aiaaic_handles_float_taxonomy_fields():
    raw = {
        "AIAAIC ID#": "AIAAIC9999",
        "Headline": "Algorithm caused wrongful arrest",
        "External harm (taxonomy)": float("nan"),
        "Consequence (taxonomy)": 3.0,
        "Summary/links": "https://example.com/aiaaic-story",
    }
    record = normalize(raw, Source.AIAAIC, ingested_at=INGESTED_AT)
    assert record.source_id == "AIAAIC9999"
    assert record.severity == Severity.HIGH


def test_parse_date_handles_partial_aiaaic_values():
    from sentinel.pipeline.normalize import _parse_date

    assert _parse_date("2018-") == date(2018, 1, 1)
    assert _parse_date("2018-06") == date(2018, 6, 1)
    assert _parse_date("2018-06-15") == date(2018, 6, 15)
    assert _parse_date("not-a-date") is None


@pytest.mark.skipif(
    not DEFAULT_ATLAS_PATH.exists(),
    reason="ATLAS YAML not downloaded locally",
)
def test_normalize_maps_jailbreak_to_atlas():
    atlas = AtlasTaxonomy.from_yaml()
    raw = {
        "incident_id": 99,
        "title": "Jailbreak bypasses ChatGPT safety filters",
        "description": "Users discovered a prompt injection jailbreak.",
        "date": "2024-01-01",
        "AllegedDeployerOfAISystem": [{"name": "OpenAI"}],
    }
    record = normalize(raw, Source.AIID, ingested_at=INGESTED_AT, atlas=atlas)
    assert record.atlas_technique == "AML.T0054"


@pytest.mark.skipif(
    not DEFAULT_ATLAS_PATH.exists(),
    reason="ATLAS YAML not downloaded locally",
)
def test_normalize_maps_nvd_to_supply_chain_default():
    atlas = AtlasTaxonomy.from_yaml()
    raw = {
        "search_keyword": "pytorch",
        "cve": {
            "id": "CVE-2024-0001",
            "published": "2024-01-01T00:00:00.000",
            "descriptions": [{"lang": "en", "value": "Buffer overflow in library."}],
            "metrics": {"cvssMetricV31": [{"cvssData": {"baseScore": 5.0}}]},
        },
    }
    record = normalize(raw, Source.NVD, ingested_at=INGESTED_AT, atlas=atlas)
    assert record.atlas_technique == "AML.T0010.001"
