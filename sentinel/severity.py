"""Severity normalization helpers — see docs/severity_normalization.md."""

from __future__ import annotations

import math
from typing import Any

from sentinel.models import Severity

CVSS_CRITICAL_MIN = 9.0
CVSS_HIGH_MIN = 7.0
CVSS_MEDIUM_MIN = 4.0
CVSS_LOW_MIN = 0.1


def cvss_to_severity(score: float | None) -> Severity:
    """Map a CVSS base score (0–10) to the shared five-point scale."""
    if score is None:
        return Severity.INFORMATIONAL
    if score >= CVSS_CRITICAL_MIN:
        return Severity.CRITICAL
    if score >= CVSS_HIGH_MIN:
        return Severity.HIGH
    if score >= CVSS_MEDIUM_MIN:
        return Severity.MEDIUM
    if score >= CVSS_LOW_MIN:
        return Severity.LOW
    return Severity.INFORMATIONAL


def cvss_label_to_severity(label: str | None) -> Severity | None:
    """Map NVD textual severity labels when numeric score is missing."""
    if not label:
        return None
    mapping = {
        "CRITICAL": Severity.CRITICAL,
        "HIGH": Severity.HIGH,
        "MEDIUM": Severity.MEDIUM,
        "LOW": Severity.LOW,
        "NONE": Severity.INFORMATIONAL,
    }
    return mapping.get(label.upper())


def _coerce_harm_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    return text


def qualitative_harm_to_severity(*texts: Any) -> Severity:
    """Heuristic mapping for AIID/AIAAIC qualitative harm descriptions."""
    combined = " ".join(
        text for item in texts if (text := _coerce_harm_text(item))
    ).lower()
    if not combined:
        return Severity.INFORMATIONAL

    critical_terms = (
        "death",
        "fatal",
        "killed",
        "suicide",
        "mass shooting",
        "sexual violence",
        "child",
    )
    high_terms = (
        "injury",
        "jail",
        "arrest",
        "discriminat",
        "bias",
        "leak",
        "breach",
        "exploit",
        "harm",
        "wrongful",
    )
    medium_terms = (
        "controvers",
        "backlash",
        "misleading",
        "inaccurate",
        "privacy",
        "surveillance",
    )

    if any(term in combined for term in critical_terms):
        return Severity.CRITICAL
    if any(term in combined for term in high_terms):
        return Severity.HIGH
    if any(term in combined for term in medium_terms):
        return Severity.MEDIUM
    return Severity.LOW
