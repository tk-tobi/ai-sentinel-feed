#!/usr/bin/env bash
# Export the current database to docker/seed/incidents.jsonl for the all-in-one image.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

PYTHON="${PYTHON:-python3}"
if [[ -x "${ROOT_DIR}/.venv/bin/python" ]]; then
  PYTHON="${ROOT_DIR}/.venv/bin/python"
fi

export PYTHONPATH="${ROOT_DIR}${PYTHONPATH:+:${PYTHONPATH}}"

"${PYTHON}" -m sentinel.pipeline.export
mkdir -p docker/seed
cp data/exports/incidents.jsonl docker/seed/incidents.jsonl
lines="$(wc -l < docker/seed/incidents.jsonl | tr -d ' ')"
echo "Wrote docker/seed/incidents.jsonl (${lines} records)"
