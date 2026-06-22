"""Heuristic MITRE ATLAS technique mapping for normalized incidents."""

from __future__ import annotations

from sentinel.models import IncidentRecord, Source, UNMAPPED_TECHNIQUE
from sentinel.sources.atlas import AtlasTaxonomy

# Ordered most-specific first; first pattern match wins.
_TECHNIQUE_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("AML.T0054", ("jailbreak", "jail break", "jail-break")),
    ("AML.T0051", ("prompt injection", "prompt inject", "inject prompt")),
    ("AML.T0061", ("self-replication", "self replication", "self-replicat")),
    ("AML.T0056", ("system prompt", "extract prompt", "leak system prompt")),
    ("AML.T0057", ("data leak", "data leakage", "training data leak", "leaked data")),
    ("AML.T0071", ("rag injection", "false rag", "poisoned rag", "retrieval poison")),
    ("AML.T0088", ("deepfake", "deep fake", "deep-fake", "synthetic media")),
    ("AML.T0052.001", ("deepfake phish", "deepfake scam")),
    ("AML.T0052", ("phishing", "phish", "spearphish", "scam email")),
    ("AML.T0073", ("impersonat", "impersonation", "voice clone")),
    ("AML.T0020", ("training data poison", "data poisoning", "poison dataset")),
    ("AML.T0018.000", ("model poison", "poisoned model")),
    ("AML.T0043.004", ("backdoor trigger", "trojan model")),
    ("AML.T0024.002", ("model extract", "model theft", "steal model", "model stealing")),
    ("AML.T0024", ("exfiltrat", "membership inference")),
    ("AML.T0029", ("denial of service", "denial-of-service", " dos ", "ddos")),
    ("AML.T0043", ("adversarial example", "adversarial attack", "adversarial input")),
    ("AML.T0062", ("hallucinat",)),
    ("AML.T0048.002", ("misinformation", "disinformation", "misinfo", "disinfo")),
    (
        "AML.T0048.003",
        (
            "privacy",
            "surveillance",
            "surveil",
            "discriminat",
            "bias",
            "fairness",
            "civil liberties",
        ),
    ),
    ("AML.T0048", (" reputational harm", "financial harm", "societal harm", "user harm")),
    ("AML.T0049", ("remote code execution", "arbitrary code", "code execution", " rce ")),
)

_NVD_DEFAULT_TECHNIQUE = "AML.T0010.001"


def _search_text(record: IncidentRecord) -> str:
    parts = [record.title, record.description, record.system or "", record.vendor or ""]
    parts.extend(record.tags)
    return " ".join(parts).lower()


def map_incident_to_atlas(
    record: IncidentRecord,
    atlas: AtlasTaxonomy,
) -> tuple[str, str | None]:
    """Return (technique_id, tactic_name) for a normalized incident."""
    text = _search_text(record)

    for technique_id, patterns in _TECHNIQUE_RULES:
        if any(pattern in text for pattern in patterns):
            if atlas.get_technique(technique_id):
                return technique_id, atlas.resolve_tactic_name(technique_id)

    if record.source == Source.NVD and atlas.get_technique(_NVD_DEFAULT_TECHNIQUE):
        return _NVD_DEFAULT_TECHNIQUE, atlas.resolve_tactic_name(_NVD_DEFAULT_TECHNIQUE)

    return UNMAPPED_TECHNIQUE, None


def apply_atlas_mapping(
    record: IncidentRecord,
    atlas: AtlasTaxonomy | None,
) -> IncidentRecord:
    if atlas is None:
        return record
    technique_id, tactic_name = map_incident_to_atlas(record, atlas)
    return record.model_copy(
        update={
            "atlas_technique": technique_id,
            "atlas_tactic": tactic_name,
        }
    )
