# CDC jumpstart (from ai-sentinel-feed)

Paste this into a new agent chat when starting a Change Data Capture project that uses this incident corpus as the source database.

## Goal

Build a CDC pipeline that streams changes from a **living** Postgres `incidents` table (inserts/updates from periodic ingest), not a one-shot dump. Downstream can be Kafka, Debezium → sink, Flink, DuckDB, etc. — pick one and keep scope small.

## Source of truth for data

AWS RDS for this project was **destroyed** (2026-08). Do **not** look for App Runner / RDS.

Use local Postgres instead:

| Artifact | Path / command |
| -------- | -------------- |
| Seed JSONL (~4.4k rows) | `docker/seed/incidents.jsonl` or `data/exports/incidents.jsonl` |
| Load seed | `docker compose up -d` then `python -m sentinel.pipeline.seed --force` |
| Fresh real writes | `python -m sentinel.pipeline.ingest --source all` (NVD / AIID / AIAAIC) |
| Schema / models | `sentinel/models.py`, Postgres via `sentinel/pipeline/store.py` |
| Env | `.env` from `.env.example`; default `DATABASE_URL=postgresql://sentinel:sentinel@localhost:5433/sentinel` |

Optional ML snapshot (static, not for CDC): [HuggingFace `tk-tobi/ai-sentinel-feed`](https://huggingface.co/datasets/tk-tobi/ai-sentinel-feed).

Optional all-in-one demo (API + Streamlit + embedded Postgres): `ghcr.io/tk-tobi/ai-sentinel-feed:latest` — fine for exploring data; for CDC prefer `docker compose` Postgres so you control WAL / logical replication settings.

## Suggested first milestones

1. Local Postgres up; seed loaded; `SELECT count(*) FROM incidents` ≈ 4.3k+.
2. Enable logical replication (`wal_level=logical` or equivalent) if using Debezium / pgoutput.
3. Create publication on `incidents` (and any related tables if added later).
4. Run ingest once and confirm the CDC consumer sees new rows (or run a tiny insert script if ingest is too heavy for a first demo).
5. Document slot / lag / failure restart behavior.

## Do not

- Recreate AWS App Runner unless explicitly asked (closed to new AWS customers after 2026-04-30; prefer ECS Express / ECS+ALB if hosting later).
- Assume Streamlit Cloud or the old `*.awsapprunner.com` URL still exist (torn down).
- Commit secrets, `terraform.tfvars`, or `tfplan*`.

## Repo context

- Project: `ai-sentinel-feed` (GitHub `tk-tobi/ai-sentinel-feed`)
- Ingest entrypoint: `python -m sentinel.pipeline.ingest`
- Status: hosted AWS stack torn down; GHCR image + HuggingFace dataset kept; README describes archived production.

## One-liner prompt

> Use `docs/cdc_jumpstart.md` in ai-sentinel-feed: stand up local Postgres from seed, enable logical CDC on `incidents`, and stream ingest-driven changes into [choose sink]. Do not recreate the old AWS stack.
