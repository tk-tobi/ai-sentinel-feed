#!/usr/bin/env bash
# Full historical ingest: all sources → Postgres → JSONL exports.
#
# Local (default):
#   ./scripts/historical_load.sh
#
# RDS (after terraform apply — point DATABASE_URL at RDS or use ECS):
#   DATABASE_URL='postgresql://...' ./scripts/historical_load.sh --target rds
#
# RDS is private in Terraform; prefer the one-off ECS task from terraform output:
#   terraform -chdir=infra/terraform/environments/dev output run_ingest_task_command
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"
export PYTHONPATH="${ROOT_DIR}${PYTHONPATH:+:${PYTHONPATH}}"

TARGET="local"
SOURCES="aiaaic aiid nvd"
SKIP_EXPORT=0
SKIP_DOCKER=0

usage() {
  cat <<'EOF'
Usage: ./scripts/historical_load.sh [options]

Options:
  --target local|rds   local starts docker-compose Postgres (default: local)
  --source NAME        Run one source (aiaaic|aiid|nvd) instead of all three
  --skip-export        Ingest only; skip JSONL export step
  --skip-docker        Do not start docker compose (use existing DATABASE_URL)
  -h, --help           Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target)
      TARGET="$2"
      shift 2
      ;;
    --source)
      SOURCES="$2"
      shift 2
      ;;
    --skip-export)
      SKIP_EXPORT=1
      shift
      ;;
    --skip-docker)
      SKIP_DOCKER=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
elif [[ ! -f .env ]] && [[ "${TARGET}" == "local" ]]; then
  echo "No .env found — copying from .env.example"
  cp .env.example .env
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

PYTHON="${PYTHON:-python3}"
if [[ -x "${ROOT_DIR}/.venv/bin/python" ]]; then
  PYTHON="${ROOT_DIR}/.venv/bin/python"
fi

echo "==> Target: ${TARGET}"
echo "==> Python: ${PYTHON}"
echo "==> Sources: ${SOURCES}"

if [[ "${TARGET}" == "local" && "${SKIP_DOCKER}" -eq 0 ]]; then
  if ! docker info >/dev/null 2>&1; then
    echo "Docker is not running. Start Docker Desktop, then re-run this script." >&2
    echo "Or use --skip-docker with a working DATABASE_URL in .env" >&2
    exit 1
  fi

  POSTGRES_PORT="${POSTGRES_PORT:-5432}"
  echo "==> Starting Postgres (host port ${POSTGRES_PORT})..."
  POSTGRES_PORT="${POSTGRES_PORT}" docker compose up -d

  echo "==> Waiting for Postgres healthcheck..."
  for _ in $(seq 1 30); do
    if POSTGRES_PORT="${POSTGRES_PORT}" docker compose exec -T db pg_isready -U sentinel -d sentinel >/dev/null 2>&1; then
      break
    fi
    sleep 2
  done
  POSTGRES_PORT="${POSTGRES_PORT}" docker compose exec -T db pg_isready -U sentinel -d sentinel
fi

if [[ "${TARGET}" == "rds" ]]; then
  if [[ "${DATABASE_URL:-}" == *"localhost"* ]]; then
    echo "WARNING: DATABASE_URL still points at localhost. Set RDS URL from:" >&2
    echo "  terraform -chdir=infra/terraform/environments/dev output -raw database_url" >&2
    echo "Or run ingest inside the VPC via ECS (see run_ingest_task_command output)." >&2
  fi
fi

echo "==> Checking database connection..."
"${PYTHON}" scripts/check_db.py

for source_name in ${SOURCES}; do
  echo ""
  echo "==> Ingesting source: ${source_name}"
  "${PYTHON}" -m sentinel.pipeline.ingest --source "${source_name}"
done

if [[ "${SKIP_EXPORT}" -eq 0 ]]; then
  echo ""
  echo "==> Exporting JSONL snapshots..."
  "${PYTHON}" -m sentinel.pipeline.export
fi

echo ""
echo "==> Load summary"
"${PYTHON}" scripts/summarize_load.py

echo ""
echo "Done. Next: fill observations in NOTES.md, then point Streamlit/API at this DATABASE_URL."
