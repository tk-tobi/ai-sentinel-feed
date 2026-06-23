# ai-sentinel-feed

A data pipeline that continuously collects, normalizes, and exposes documented AI failures, vulnerabilities, and adversarial incidents from public sources. Structured and accessible for visualization, analysis, search, and downstream ML use.

---

## What this is

AI incident data is scattered. Vulnerability databases, academic trackers, and adversarial ML research each capture a different slice of this problem space. `ai-sentinel-feed` pulls data from all of them, normalizes records against a shared schema mapped to the [MITRE ATLAS](https://atlas.mitre.org/) adversarial ML taxonomy, and exposes the unified dataset through:

- A **read-only REST API** (FastAPI)
- An **interactive dashboard** (Streamlit / Streamlit Cloud)
- **Versioned JSONL exports** and **HuggingFace Hub** for ML pipelines

This is a living feed, not a one-time scrape. New records are ingested on a daily schedule; each export is timestamped.

**Design principle:** The **ingest pipeline** and **API / consumption layer** are separate. They share storage (Postgres) but deploy, scale, and fail independently. Ingest runs as a batch job (Playwright for AIID, long NVD fetches); the API is stateless and read-only.

---

## Quick start (Docker)

**One step:** pull the pre-built image and run (no clone, no Python, no historical load):

```bash
docker run -d \
  --name ai-sentinel-feed \
  -p 8000:8000 -p 8501:8501 \
  -v sentinel_pgdata:/var/lib/postgresql/data \
  ghcr.io/tk-tobi/ai-sentinel-feed:latest
```

| Service   | URL                        |
| --------- | -------------------------- |
| API       | http://localhost:8000      |
| API docs  | http://localhost:8000/docs |
| Dashboard | http://localhost:8501      |

Postgres starts inside the container; ~4.4k seeded incidents load on first boot. Data persists in the `sentinel_pgdata` volume.

**Compose alternative** (from a clone):

```bash
docker compose -f docker-compose.local.yml up -d
```

The Dockerfile and seed file live in the repo for **transparency and reproducibility:** consumers pull the published image; they do not need to build unless developing. See [`docker/README.md`](docker/README.md) for maintainers (refresh seed, build from source, CI publish to GHCR).

---

## Architecture

### Local development

**Option A: all-in-one Docker** (recommended for trying the feed): see [Quick start](#quick-start-docker) above.

**Option B: from source** (ingest, tests, pipeline changes):

```mermaid
flowchart LR
    subgraph sources [Round1Sources]
        NVD[NVD]
        AIID[AIID]
        AIAAIC[AIAAIC]
        ATLAS[MITRE_ATLAS]
    end

    subgraph ingest [IngestPipeline]
        fetch[fetch]
        raw[raw_JSONL]
        norm[normalize_dedupe]
        pg[(PostgreSQL)]
        exp[JSONL_exports]
    end

    subgraph consume [Consumption]
        api[FastAPI]
        dash[Streamlit]
        hf[HuggingFace_Hub]
    end

    sources --> fetch --> raw --> norm --> pg
    norm --> exp --> hf
    pg --> api
    pg --> dash
```



### Production (AWS, dev environment live)

**API (App Runner):** `https://hkfxqsyja3.us-east-2.awsapprunner.com`  
Health: `GET /health` → `{"status":"ok"}`

| Layer            | Local (Docker)                       | Local (from source)                  | AWS (dev)                          |
| ---------------- | ------------------------------------ | ------------------------------------ | ---------------------------------- |
| App + DB         | **Single image** (GHCR)              | `docker compose` Postgres + Python   | **RDS** + **App Runner**           |
| Ingest scheduler | N/A (pre-seeded)                     | Manual / cron                        | **EventBridge** (daily)            |
| Ingest compute   | N/A                                  | `python -m sentinel.pipeline.ingest` | **ECS Fargate** (Playwright image) |
| Raw storage      | baked seed                           | `data/raw/`                          | **S3**                             |
| Structured       | embedded Postgres                    | Docker Postgres                      | **RDS PostgreSQL**                 |
| Exports          | -                                    | `data/exports/`                      | **S3**                             |
| API              | `:8000` in container                 | `uvicorn`                            | **App Runner** ✓                   |
| Dashboard        | `:8501` in container                 | `streamlit run`                      | **Streamlit Cloud** ✓ (via API)    |
| Secrets          | defaults in image                    | `.env`                               | **Secrets Manager**                |
| ML access        | -                                    | local JSONL                          | **HuggingFace Hub** ✓              |

Infrastructure is defined in [`infra/terraform/`](infra/terraform/). Spin up and tear down:

```bash
./infra/scripts/apply.sh dev      # infra → ECR push → App Runner
./infra/scripts/teardown.sh dev   # terraform destroy (dev-safe defaults)
```

See [`infra/terraform/README.md`](infra/terraform/README.md) for details.

---

## Data Sources

### Round 1 (Live)


| Source                                                     | What it contributes                                                                                |
| ---------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| [NVD / CVE](https://nvd.nist.gov/developers)               | AI/ML library CVEs (`pytorch`, `tensorflow`, `langchain`, `huggingface`) with CVSS severity scores |
| [AI Incident Database (AIID)](https://incidentdatabase.ai) | Documented real-world AI failures, structured by involved system and harm type                     |
| [AIAAIC](https://www.aiaaic.org)                           | Documented AI controversies and algorithmic harms, catches incidents outside technical DBs        |
| [MITRE ATLAS](https://github.com/mitre-atlas/atlas-data)   | Adversarial ML tactic/technique taxonomy, classification layer across all sources                 |


Source exploration notes: `[docs/source_exploration.md](docs/source_exploration.md)`

### Round 2 (Planned)

GitHub Issues · HuggingFace Advisories · ArXiv · News/RSS

---

## Schema

Every record, regardless of source, is normalized into a shared structure:

```json
{
  "id": "sha256 hash of (source + source_id)",
  "source": "NVD | AIID | AIAAIC | ATLAS | GitHub",
  "source_id": "original identifier from source",
  "title": "string",
  "description": "string",
  "incident_date": "YYYY-MM-DD",
  "ingested_at": "ISO 8601 timestamp",
  "vendor": "OpenAI | Meta | Google | HuggingFace | ...",
  "system": "GPT-4 | Llama 3 | Gemini | ...",
  "atlas_technique": "AML.T0051 | AML.T0054 | ...",
  "atlas_tactic": "ML Attack Staging | Exfiltration | ...",
  "severity": "critical | high | medium | low | informational",
  "tags": ["jailbreak", "prompt-injection", "data-poisoning"],
  "url": "source URL",
  "raw": {}
}
```

**Notes on normalization:**

- `atlas_technique` maps each incident to the closest MITRE ATLAS technique via keyword heuristics (`sentinel/pipeline/atlas_map.py`). NVD library CVEs default to supply-chain (`AML.T0010.001`); unmatched records stay `unmapped`.
- `severity` normalizes CVSS scores (NVD) and qualitative harm ratings (AIID/AIAAIC) onto a shared five-point scale. See `[docs/severity_normalization.md](docs/severity_normalization.md)`.
- `raw` stores the untouched source payload. Schema changes re-normalize from raw, no re-scraping required.
- PII patterns in `description` are masked during normalization (emails, phone numbers, SSN-like strings).

---

## Storage

```
Raw layer     →   data/raw/{source}/YYYY-MM-DD.jsonl   (untouched source output; S3 in prod)
Structured    →   PostgreSQL                            (normalized records; RDS in prod)
Exports       →   data/exports/                         (JSONL dumps; S3 in prod)
```

---

## Outputs

### API

FastAPI: read-only, no ingest logic. Local base URL: `http://localhost:8000`

```
GET /health                     # health check
GET /incidents                  # paginated list; filter by source, vendor, severity, date
GET /incidents/{id}             # single record
GET /incidents/stats            # counts by vendor, technique, severity over time
GET /feed                       # latest 50 records
GET /atlas/techniques           # ATLAS technique frequency (mapped records only)
```

Docs: `/docs` (Swagger) · `/redoc`

```bash
# Local (from source)
uvicorn sentinel.api.main:app --reload
# or: ./scripts/run_api.sh
```

### Dashboard

Streamlit: volume charts, severity distribution, ATLAS frequency, vendor×tactic table, searchable incidents.

```bash
# Local (from source)
streamlit run sentinel/dashboard/app.py
# or: ./scripts/run_dashboard.sh

# Docker: included in ghcr.io/tk-tobi/ai-sentinel-feed (port 8501)
# Production: Streamlit Community Cloud, set secret `SENTINEL_API_URL` to App Runner URL
```

### Data dumps & HuggingFace

```bash
python -m sentinel.pipeline.export
```

Writes to `data/exports/`:

```
incidents.jsonl                  # all normalized records
incidents_atlas_mapped.jsonl     # ATLAS-mapped records only
jailbreaks.jsonl                 # jailbreak / prompt-injection tagged records
manifest_{timestamp}.json        # export metadata
```

**HuggingFace Hub** (sync after each full ingest, or manually):

```bash
# From production API (no RDS access needed)
export HF_TOKEN=hf_...
python -m sentinel.pipeline.huggingface \
  --api-url https://hkfxqsyja3.us-east-2.awsapprunner.com

# From local Postgres after export
python -m sentinel.pipeline.export --hub
```

```python
from datasets import load_dataset
ds = load_dataset("tk-tobi/ai-sentinel-feed")
```

---

## Project structure

```
ai-sentinel-feed/
├── sentinel/
│   ├── sources/           # nvd.py, aiid.py, aiaaic.py, atlas.py
│   ├── pipeline/          # ingest, normalize, atlas_map, seed, store, read, export
│   ├── api/main.py        # FastAPI (read-only)
│   ├── dashboard/app.py   # Streamlit
│   ├── models.py
│   ├── severity.py
│   └── config.py
├── docker/                # Dockerfile, entrypoint, seed JSONL, README
├── infra/
│   ├── terraform/         # AWS: S3, RDS, ECR, ECS ingest, App Runner, Secrets
│   └── scripts/           # apply.sh, teardown.sh
├── scripts/               # historical_load, run_api, run_dashboard, export_docker_seed
├── data/raw|exports|atlas/
├── docs/
├── tests/
├── .github/workflows/     # docker-publish.yml → GHCR
├── docker-compose.yml     # Postgres only (dev ingest)
├── docker-compose.local.yml   # pull pre-built all-in-one image
├── docker-compose.build.yml   # optional: build from source
├── .env.example
├── requirements/          # dev.txt, docker.txt, api.txt, ingest.txt
├── requirements.txt       # shim → requirements/dev.txt
```

---

## Setup (from source)

For pipeline development, ingest, and tests; not required if you only use the Docker image.

```bash
git clone https://github.com/tk-tobi/ai-sentinel-feed
cd ai-sentinel-feed

python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# AIID connector requires Playwright + Chromium (one-time)
pip install playwright
python -m playwright install chromium

cp .env.example .env          # set NVD_API_KEY, DATABASE_URL
docker compose up -d            # Postgres on POSTGRES_PORT (default 5433 in .env.example)

# Full historical load (or use pre-seeded Docker image instead)
./scripts/historical_load.sh

# Re-apply ATLAS mapping after rule changes
python -m sentinel.pipeline.remap_atlas

# Export JSONL + refresh Docker seed for next image build
python -m sentinel.pipeline.export
./scripts/export_docker_seed.sh

# API + dashboard
./scripts/run_api.sh
./scripts/run_dashboard.sh
```

**Environment variables** (see `[.env.example](.env.example)`):

```
NVD_API_KEY=
NVD_KEYWORDS=pytorch,tensorflow,langchain,huggingface
AIID_GRAPHQL_URL=https://incidentdatabase.ai/api/graphql
AIAAIC_CSV_URL=https://docs.google.com/spreadsheets/d/.../export?format=csv&gid=...
DATABASE_URL=postgresql://sentinel:sentinel@localhost:5432/sentinel
```

`NVD_API_KEY` is strongly recommended, unauthenticated NVD requests are slow (~6s between calls).

---

## Production deployment

| Component     | Service                   | Status (dev) |
| ------------- | ------------------------- | ------------ |
| Ingest job    | ECS Fargate + EventBridge | Provisioned; nightly sync includes HF publish when `HF_TOKEN` set |
| API           | AWS App Runner            | **Live:** see `terraform output api_service_url` |
| Database      | RDS PostgreSQL            | **Loaded** (~4.3k incidents) |
| Raw / exports | S3                        | Provisioned |
| Dashboard     | Streamlit Cloud           | **Live** |
| ML dataset    | HuggingFace Hub           | Publish via `python -m sentinel.pipeline.huggingface` |

### Deploy workflow

```bash
# 1. Authenticate (required before terraform / ECR / ECS)
aws login
eval "$(aws configure export-credentials --format env)"

# 2. Infrastructure + App Runner (from repo root)
./infra/scripts/apply.sh dev
# Or recover a partial deploy:
./infra/scripts/finish_api_deploy.sh dev --skip-push

# 3. Push container images (API already pushed if App Runner is live)
./infra/scripts/push_ecr.sh dev              # both images
./infra/scripts/push_ecr.sh dev --api-only   # API only
./infra/scripts/push_ecr.sh dev --ingest-only  # ingest only (large Playwright image)

# 4. Load historical data into RDS (one-off ECS task, ~30–90 min)
./scripts/historical_load_rds.sh dev

# 5. Verify
curl "$(cd infra/terraform/environments/dev && terraform output -raw api_service_url)/health"
curl "$(cd infra/terraform/environments/dev && terraform output -raw api_service_url)/incidents?page_size=1"
```

**Teardown (dev):** `./infra/scripts/teardown.sh dev` uses `skip_final_snapshot` and `force_destroy` on buckets.

Image definitions: `docker/Dockerfile.api` (App Runner), `docker/Dockerfile.ingest` (ECS).  
Detailed infra notes: [`infra/terraform/README.md`](infra/terraform/README.md).


---

## Potential future improvements

- Round 2 sources: GitHub Issues, HuggingFace Advisories, ArXiv, News/RSS
- Richer ATLAS mapping (ML classifier, manual review queue for `unmapped`)
- Cross-source deduplication (fuzzy match on title/date across AIID and AIAAIC)
- Incremental ingest (cursors / delta fetch instead of full re-pull each run)
- S3 upload hooks for raw snapshots and JSONL exports
- Eval question sets and semantics visualization (UMAP / WizMap) over the corpus
- Multi-environment Terraform (`staging` / `prod`) with remote state and CI/CD
- Observability: structured logs, ingest failure alarms, deeper `/health` checks
- API authentication and rate limiting for programmatic consumers
- WAF, TLS everywhere, least-privilege IAM, and Secrets Manager rotation
- Database indexes and full-text search on title/description
- API caching (Redis / CDN) and RDS read replicas for scale
- AIID Playwright session reuse and parallel NVD keyword fetch
- Server-side dashboard filters instead of loading the full dataset client-side
- Full-text search API, webhooks/RSS for new critical incidents, API versioning (`/v1/`)
- Next.js dashboard on Vercel calling the public API

---

## Author

**Oluwatobi Adeyefa**  
[tobi.adeyefa@nyu.edu](mailto:tobi.adeyefa@nyu.edu) · [tobi.adeyefa1@gmail.com](mailto:tobi.adeyefa1@gmail.com) · [LinkedIn](https://linkedin.com/in/oadeyefa/) · [Portfolio](https://tk-tobi.github.io/tobiA/)