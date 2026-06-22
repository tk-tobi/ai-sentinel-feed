#!/usr/bin/env bash
set -euo pipefail

PGDATA="${PGDATA:-/var/lib/postgresql/data}"
export PGDATA

mkdir -p "${PGDATA}"
chown -R postgres:postgres "${PGDATA}"

start_postgres() {
  if [[ ! -f "${PGDATA}/PG_VERSION" ]]; then
    echo "==> Initializing PostgreSQL data directory"
    su postgres -c "initdb -D ${PGDATA}"
    su postgres -c "pg_ctl -D ${PGDATA} -o '-c listen_addresses=127.0.0.1' -w start"
    su postgres -c "psql -v ON_ERROR_STOP=1 <<-SQL
CREATE USER sentinel WITH PASSWORD 'sentinel' SUPERUSER;
CREATE DATABASE sentinel OWNER sentinel;
SQL"
    su postgres -c "pg_ctl -D ${PGDATA} -m fast -w stop"
  fi

  echo "==> Starting PostgreSQL"
  su postgres -c "pg_ctl -D ${PGDATA} -o '-c listen_addresses=127.0.0.1' -w start"
}

stop_postgres() {
  su postgres -c "pg_ctl -D ${PGDATA} -m fast -w stop" 2>/dev/null || true
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
