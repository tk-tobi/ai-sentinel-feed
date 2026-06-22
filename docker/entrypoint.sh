#!/usr/bin/env bash
set -euo pipefail

PGDATA="${PGDATA:-/var/lib/postgresql/data}"
export PGDATA

PG_BIN="$(find /usr/lib/postgresql -maxdepth 3 -type f -name initdb -print -quit 2>/dev/null)"
PG_BIN="$(dirname "${PG_BIN}")"
if [[ ! -x "${PG_BIN}/initdb" ]]; then
  echo "ERROR: PostgreSQL server binaries not found under /usr/lib/postgresql" >&2
  exit 1
fi
export PATH="${PG_BIN}:${PATH}"

mkdir -p "${PGDATA}"
chown -R postgres:postgres "${PGDATA}"

postgres_su() {
  su postgres -c "$*"
}

start_postgres() {
  if [[ ! -f "${PGDATA}/PG_VERSION" ]]; then
    echo "==> Initializing PostgreSQL data directory"
    postgres_su "${PG_BIN}/initdb -D ${PGDATA}"
    postgres_su "${PG_BIN}/pg_ctl -D ${PGDATA} -o '-c listen_addresses=127.0.0.1' -w start"
    postgres_su "${PG_BIN}/psql -v ON_ERROR_STOP=1 <<-SQL
CREATE USER sentinel WITH PASSWORD 'sentinel' SUPERUSER;
CREATE DATABASE sentinel OWNER sentinel;
SQL"
    postgres_su "${PG_BIN}/pg_ctl -D ${PGDATA} -m fast -w stop"
  fi

  echo "==> Starting PostgreSQL"
  postgres_su "${PG_BIN}/pg_ctl -D ${PGDATA} -o '-c listen_addresses=127.0.0.1' -w start"
}

stop_postgres() {
  postgres_su "${PG_BIN}/pg_ctl -D ${PGDATA} -m fast -w stop" 2>/dev/null || true
}

trap stop_postgres EXIT

start_postgres

echo "==> Waiting for PostgreSQL"
until pg_isready -h 127.0.0.1 -U sentinel -d sentinel >/dev/null 2>&1; do
  sleep 1
done

export DATABASE_URL="${DATABASE_URL:-postgresql://sentinel:sentinel@127.0.0.1:5432/sentinel}"
export PYTHONPATH=/app

echo "==> Seeding database (skipped if already populated)"
python -m sentinel.pipeline.seed

echo "==> Starting API and dashboard"
exec supervisord -n -c /app/docker/supervisord.conf
