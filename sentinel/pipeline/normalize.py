"""Normalize raw source records into unified IncidentRecord objects."""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Any, Callable
from urllib.parse import urlparse

from sentinel.models import IncidentRecord, Source, UNMAPPED_TECHNIQUE
from sentinel.severity import (
    cvss_label_to_severity,
    cvss_to_severity,
    qualitative_harm_to_severity,
)
from sentinel.sources.atlas import AtlasTaxonomy

_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
_PHONE_RE = re.compile(
    r"\b(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?){2}\d{4}\b"
)
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")

Normalizer = Callable[[dict[str, Any], datetime, AtlasTaxonomy | None], IncidentRecord]


def mask_pii(text: str) -> str:
    """Redact common PII patterns from free-text descriptions."""
    masked = _EMAIL_RE.sub("[REDACTED_EMAIL]", text)
    masked = _PHONE_RE.sub("[REDACTED_PHONE]", masked)
    masked = _SSN_RE.sub("[REDACTED_SSN]", masked)
    return masked


def normalize(
    raw: dict[str, Any],
    source: Source,
    *,
    ingested_at: datetime | None = None,
    atlas: AtlasTaxonomy | None = None,
) -> IncidentRecord:
    """Dispatch to a source-specific normalizer and apply shared post-processing."""
    ingested_at = ingested_at or datetime.now(timezone.utc)
    normalizers: dict[Source, Normalizer] = {
        Source.NVD: _normalize_nvd,
        Source.AIID: _normalize_aiid,
        Source.AIAAIC: _normalize_aiaaic,
    }
    try:
        normalizer = normalizers[source]
    except KeyError as exc:
        raise NotImplementedError(
            f"No normalizer implemented for source {source.value}"
        ) from exc

    record = normalizer(raw, ingested_at, atlas)
    record.description = mask_pii(record.description)
    return record


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    value = str(value).strip()
    if len(value) == 4 and value.isdigit():
        return date(int(value), 1, 1)
    return date.fromisoformat(value[:10])


def _first_url(text: str | None) -> str | None:
    if not text:
        return None
    for token in re.split(r"\s+", text):
        if token.startswith("http"):
            parsed = urlparse(token.rstrip(".,;)"))
            if parsed.scheme and parsed.netloc:
                return token.rstrip(".,;)")
    return None


def _english_description(descriptions: list[dict[str, Any]]) -> str:
    for item in descriptions:
        if item.get("lang") == "en":
            return item.get("value", "")
    return descriptions[0].get("value", "") if descriptions else ""


def _nvd_cvss_score(cve: dict[str, Any]) -> float | None:
    metrics = cve.get("metrics", {})
    for key in ("cvssMetricV31", "cvssMetricV30"):
        for metric in metrics.get(key, []):
            score = metric.get("cvssData", {}).get("baseScore")
            if score is not None:
                return float(score)
    return None


def _nvd_cvss_label(cve: dict[str, Any]) -> str | None:
    metrics = cve.get("metrics", {})
    for key in ("cvssMetricV31", "cvssMetricV30"):
        for metric in metrics.get(key, []):
            label = metric.get("cvssData", {}).get("baseSeverity")
            if label:
                return label
    return None


def _nvd_vendor_product(cve: dict[str, Any]) -> tuple[str | None, str | None]:
    for affected in cve.get("affected", []):
        for item in affected.get("affectedData", []):
            vendor = item.get("vendor")
            product = item.get("product")
            if vendor or product:
                return vendor, product
    return None, None


def _normalize_nvd(
    raw: dict[str, Any],
    ingested_at: datetime,
    atlas: AtlasTaxonomy | None,
) -> IncidentRecord:
    cve = raw.get("cve", raw)
    source_id = cve["id"]
    vendor, product = _nvd_vendor_product(cve)
    score = _nvd_cvss_score(cve)
    severity = cvss_to_severity(score)
    if severity.value == "informational":
        label_severity = cvss_label_to_severity(_nvd_cvss_label(cve))
        if label_severity:
            severity = label_severity

    tags = []
    for weakness in cve.get("weaknesses", []):
        for desc in weakness.get("description", []):
            value = desc.get("value")
            if value:
                tags.append(value)

    title = source_id
    if product:
        title = f"{source_id}: {product}"

    return IncidentRecord.build(
        source=Source.NVD,
        source_id=source_id,
        title=title,
        description=_english_description(cve.get("descriptions", [])),
        incident_date=_parse_date(cve.get("published")),
        ingested_at=ingested_at,
        vendor=vendor,
        system=product,
        atlas_technique=UNMAPPED_TECHNIQUE,
        severity=severity,
        tags=tags,
        url=f"https://nvd.nist.gov/vuln/detail/{source_id}",
        raw=raw,
    )


def _normalize_aiid(
    raw: dict[str, Any],
    ingested_at: datetime,
    atlas: AtlasTaxonomy | None,
) -> IncidentRecord:
    source_id = str(raw["incident_id"])
    deployers = raw.get("AllegedDeployerOfAISystem") or []
    developers = raw.get("AllegedDeveloperOfAISystem") or []
    vendor = None
    if deployers:
        vendor = deployers[0].get("name")
    elif developers:
        vendor = developers[0].get("name")

    severity = qualitative_harm_to_severity(
        raw.get("title"),
        raw.get("description"),
    )

    return IncidentRecord.build(
        source=Source.AIID,
        source_id=source_id,
        title=raw.get("title", ""),
        description=raw.get("description") or "",
        incident_date=_parse_date(raw.get("date")),
        ingested_at=ingested_at,
        vendor=vendor,
        atlas_technique=UNMAPPED_TECHNIQUE,
        severity=severity,
        url=f"https://incidentdatabase.ai/cite/{source_id}",
        raw=raw,
    )


def _clean_optional(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    return text


def _normalize_aiaaic(
    raw: dict[str, Any],
    ingested_at: datetime,
    atlas: AtlasTaxonomy | None,
) -> IncidentRecord:
    source_id = str(raw["AIAAIC ID#"]).strip()
    vendor = _clean_optional(raw.get("Deployer")) or _clean_optional(raw.get("Developer"))
    system = _clean_optional(raw.get("System name")) or _clean_optional(raw.get("Technology"))
    summary = _clean_optional(raw.get("Summary/links"))

    severity = qualitative_harm_to_severity(
        raw.get("Headline"),
        raw.get("External harm (taxonomy)"),
        raw.get("Consequence (taxonomy)"),
        summary,
    )

    tags = []
    for field in (
        "Ethical issue (taxonomy)",
        "News trigger (taxonomy)",
        "Technology",
    ):
        value = _clean_optional(raw.get(field))
        if value:
            tags.append(value)

    return IncidentRecord.build(
        source=Source.AIAAIC,
        source_id=source_id,
        title=str(raw.get("Headline", "")),
        description=summary or str(raw.get("Headline", "")),
        incident_date=_parse_date(_clean_optional(raw.get("Occurred"))),
        ingested_at=ingested_at,
        vendor=vendor,
        system=system,
        atlas_technique=UNMAPPED_TECHNIQUE,
        severity=severity,
        tags=tags,
        url=_first_url(summary),
        raw=raw,
    )
