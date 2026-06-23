"""Static reference tables for the Streamlit dashboard."""

from __future__ import annotations

SEVERITY_SCALE = [
    {"severity": "critical", "meaning": "Severe harm, loss of life, systemic exploitation, major data breach"},
    {"severity": "high", "meaning": "Significant harm, injury, wrongful arrest, discrimination, active exploitation"},
    {"severity": "medium", "meaning": "Moderate harm, controversy, misleading output, privacy concerns"},
    {"severity": "low", "meaning": "Minor or limited harm"},
    {"severity": "informational", "meaning": "No harm score available, or negligible impact"},
]

CVSS_SCORE_MAP = [
    {"cvss_score": "9.0 – 10.0", "severity": "critical"},
    {"cvss_score": "7.0 – 8.9", "severity": "high"},
    {"cvss_score": "4.0 – 6.9", "severity": "medium"},
    {"cvss_score": "0.1 – 3.9", "severity": "low"},
    {"cvss_score": "0.0 / missing", "severity": "informational"},
]

QUALITATIVE_SIGNAL_MAP = [
    {"signal": "death, fatal, killed, suicide, mass shooting, sexual violence", "severity": "critical"},
    {"signal": "injury, jail, arrest, discriminat*, leak, breach, exploit, harm", "severity": "high"},
    {"signal": "controvers*, backlash, misleading, inaccurate, privacy", "severity": "medium"},
    {"signal": "other non-empty text", "severity": "low"},
    {"signal": "empty / missing", "severity": "informational"},
]
