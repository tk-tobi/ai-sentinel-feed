"""MITRE ATLAS taxonomy loader and lookup helpers."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import httpx
import yaml

from sentinel.config import ATLAS_DIR

DEFAULT_ATLAS_PATH = ATLAS_DIR / "ATLAS.yaml"
ATLAS_DOWNLOAD_URL = (
    "https://raw.githubusercontent.com/mitre-atlas/atlas-data/main/dist/ATLAS.yaml"
)


@dataclass(frozen=True)
class AtlasTechnique:
    id: str
    name: str
    description: str | None
    tactic_ids: tuple[str, ...]
    tactic_names: tuple[str, ...]
    parent_id: str | None = None


@dataclass(frozen=True)
class AtlasTactic:
    id: str
    name: str


class AtlasTaxonomy:
    """In-memory MITRE ATLAS matrix for technique/tactic resolution."""

    def __init__(
        self,
        *,
        version: str,
        tactics: dict[str, AtlasTactic],
        techniques: dict[str, AtlasTechnique],
    ) -> None:
        self.version = version
        self._tactics = tactics
        self._techniques = techniques
        self._parent_by_id = {
            tech.id: tech.parent_id
            for tech in techniques.values()
            if tech.parent_id
        }

    @classmethod
    def from_yaml(cls, path: Path | str = DEFAULT_ATLAS_PATH) -> AtlasTaxonomy:
        path = Path(path)
        data = yaml.safe_load(path.read_text())
        matrix = data["matrices"][0]

        tactics = {
            item["id"]: AtlasTactic(id=item["id"], name=item["name"])
            for item in matrix.get("tactics", [])
        }

        raw_techniques = {
            item["id"]: item for item in matrix.get("techniques", [])
        }

        techniques: dict[str, AtlasTechnique] = {}
        for tech_id, item in raw_techniques.items():
            tactic_ids = cls._resolve_tactic_ids(tech_id, raw_techniques)
            tactic_names = tuple(
                tactics[tid].name for tid in tactic_ids if tid in tactics
            )
            techniques[tech_id] = AtlasTechnique(
                id=tech_id,
                name=item["name"],
                description=item.get("description"),
                tactic_ids=tactic_ids,
                tactic_names=tactic_names,
                parent_id=item.get("specializes") or item.get("subtechnique-of"),
            )

        return cls(
            version=str(data.get("version", "unknown")),
            tactics=tactics,
            techniques=techniques,
        )

    @staticmethod
    def _resolve_tactic_ids(
        tech_id: str,
        raw_techniques: dict[str, dict],
        seen: set[str] | None = None,
    ) -> tuple[str, ...]:
        seen = seen or set()
        if tech_id in seen:
            return ()
        seen.add(tech_id)

        item = raw_techniques.get(tech_id, {})
        tactic_ids = item.get("tactics") or []
        if tactic_ids:
            return tuple(tactic_ids)

        parent_id = item.get("specializes") or item.get("subtechnique-of")
        if parent_id:
            return AtlasTaxonomy._resolve_tactic_ids(
                parent_id, raw_techniques, seen
            )
        return ()

    def get_technique(self, technique_id: str) -> AtlasTechnique | None:
        return self._techniques.get(technique_id)

    def get_tactic(self, tactic_id: str) -> AtlasTactic | None:
        return self._tactics.get(tactic_id)

    def list_techniques(self) -> list[AtlasTechnique]:
        return list(self._techniques.values())

    def resolve_tactic_name(self, technique_id: str) -> str | None:
        technique = self.get_technique(technique_id)
        if not technique or not technique.tactic_names:
            return None
        return technique.tactic_names[0]


def ensure_atlas_yaml(path: Path | str = DEFAULT_ATLAS_PATH) -> Path:
    """Download ATLAS.yaml if missing locally."""
    path = Path(path)
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    response = httpx.get(ATLAS_DOWNLOAD_URL, follow_redirects=True, timeout=60.0)
    response.raise_for_status()
    path.write_text(response.text, encoding="utf-8")
    return path


@lru_cache(maxsize=1)
def load_atlas(path: str | None = None) -> AtlasTaxonomy:
    """Load (and cache) the MITRE ATLAS taxonomy from disk."""
    yaml_path = Path(path) if path else ensure_atlas_yaml()
    return AtlasTaxonomy.from_yaml(yaml_path)
