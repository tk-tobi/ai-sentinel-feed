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

## Architecture

### Local development

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



### Production (AWS target)


| Layer            | Local                                | AWS (target)                       | GCP equivalent  |
| ---------------- | ------------------------------------ | ---------------------------------- | --------------- |
| Ingest scheduler | Manual / cron                        | **EventBridge**                    | Cloud Scheduler |
| Ingest compute   | `python -m sentinel.pipeline.ingest` | **ECS Fargate** (Playwright image) | Cloud Run Jobs  |
| Raw storage      | `data/raw/`                          | **S3**                             | Cloud Storage   |
| Structured       | Docker Postgres                      | **RDS PostgreSQL**                 | Cloud SQL       |
| Exports          | `data/exports/`                      | **S3**                             | Cloud Storage   |
| API              | `uvicorn`                            | **App Runner** (or ECS + ALB)      | Cloud Run       |
| Dashboard        | `streamlit run`                      | **Streamlit Community Cloud**      | Cloud Run       |
| Secrets          | `.env`                               | **Secrets Manager**                | Secret Manager  |
| ML access        | local JSONL                          | **HuggingFace Hub**                | HuggingFace Hub |


Infrastructure is defined in `[infra/terraform/](infra/terraform/)`. Spin up and tear down:

```bash
./infra/scripts/apply.sh dev      # terraform apply
./infra/scripts/teardown.sh dev   # terraform destroy (dev-safe defaults)
```

See `[infra/terraform/README.md](infra/terraform/README.md)` for details. Implementation status and go-live checklist live in `TODO.md` (local notes).

---

## Data Sources

### Round 1 (Live)


| Source                                                     | What it contributes                                                                                |
| ---------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| [NVD / CVE](https://nvd.nist.gov/developers)               | AI/ML library CVEs (`pytorch`, `tensorflow`, `langchain`, `huggingface`) with CVSS severity scores |
| [AI Incident Database (AIID)](https://incidentdatabase.ai) | Documented real-world AI failures, structured by involved system and harm type                     |
| [AIAAIC](https://www.aiaaic.org)                           | Documented AI controversies and algorithmic harms — catches incidents outside technical DBs        |
| [MITRE ATLAS](https://github.com/mitre-atlas/atlas-data)   | Adversarial ML tactic/technique taxonomy — classification layer across all sources                 |


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

- `atlas_technique` maps each incident to the closest MITRE ATLAS technique. NVD CVEs with no direct ATLAS analog are tagged `unmapped` and flagged for manual review.
- `severity` normalizes CVSS scores (NVD) and qualitative harm ratings (AIID/AIAAIC) onto a shared five-point scale. See `[docs/severity_normalization.md](docs/severity_normalization.md)`.
- `raw` stores the untouched source payload. Schema changes re-normalize from raw — no re-scraping required.
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

FastAPI — read-only, no ingest logic. Local base URL: `http://localhost:8000`

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
uvicorn sentinel.api.main:app --reload
```

### Dashboard

Streamlit — volume charts, severity distribution, ATLAS frequency, vendor×tactic heatmap, searchable table.

```bash
# Local
streamlit run sentinel/dashboard/app.py

# Production: Streamlit Community Cloud (connect via DATABASE_URL or API)
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

**HuggingFace Hub** (planned — sync after each ingest):

```python
from datasets import load_dataset
ds = load_dataset("your-org/ai-sentinel-feed", data_files="incidents.jsonl")
```

---

## Project structure

```
ai-sentinel-feed/
├── sentinel/
│   ├── sources/           # nvd.py, aiid.py, aiaaic.py, atlas.py
│   ├── pipeline/          # ingest, normalize, deduplicate, store, read, export
│   ├── api/main.py        # FastAPI (read-only)
│   ├── dashboard/app.py   # Streamlit
│   ├── models.py
│   ├── severity.py
│   └── config.py
├── infra/
│   ├── terraform/         # AWS: S3, RDS, ECR, ECS ingest, App Runner, Secrets
│   └── scripts/           # apply.sh, teardown.sh
├── data/raw|exports|atlas/
├── docs/
├── tests/
├── .env.example
├── docker-compose.yml     # local Postgres
└── requirements.txt
```

---

## Setup (local)

```bash
git clone https://github.com/tobiadeyefa/ai-sentinel-feed
cd ai-sentinel-feed

python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# AIID connector requires Playwright + Chromium (one-time)
pip install playwright
python -m playwright install chromium

cp .env.example .env          # set NVD_API_KEY, DATABASE_URL
docker compose up -d            # starts Postgres

# Ingest (single source or all Round 1)
python -m sentinel.pipeline.ingest --source aiaaic
python -m sentinel.pipeline.ingest --source all
python -m sentinel.pipeline.ingest --source all --dry-run   # no DB write

# Export JSONL
python -m sentinel.pipeline.export

# API + dashboard
uvicorn sentinel.api.main:app --reload
streamlit run sentinel/dashboard/app.py
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


| Component     | Service                   |
| ------------- | ------------------------- |
| Ingest job    | ECS Fargate + EventBridge |
| API           | AWS App Runner            |
| Database      | RDS PostgreSQL            |
| Raw / exports | S3                        |
| Dashboard     | Streamlit Cloud           |
| ML dataset    | HuggingFace Hub           |


**Teardown (dev):** `./infra/scripts/teardown.sh dev` uses `skip_final_snapshot` and `force_destroy` on buckets.

---

## Potential future improvements

- Round 2 sources: GitHub Issues, HuggingFace Advisories, ArXiv, News/RSS
- ATLAS technique mapping beyond `unmapped` heuristics for NVD CVEs
- HuggingFace Hub publish with dataset card (sync from nightly exports)
- S3 upload hooks in ingest; Docker images for ECR (ingest + API)
- API auth (API keys / IAM) for programmatic consumers
- Dashboard on Vercel (Next.js) calling the public API for product-grade UX
- Cross-source deduplication (fuzzy match on title/date across AIID and AIAAIC)
- Eval question sets and semantics visualization (UMAP / WizMap) from incident corpus

---

## Author

**Oluwatobi Adeyefa**  
[tobi.adeyefa@nyu.edu](mailto:tobi.adeyefa@nyu.edu) · [tobi.adeyefa1@gmail.com](mailto:tobi.adeyefa1@gmail.com) · [LinkedIn](https://linkedin.com/in/oadeyefa/) · [Portfolio](https://tk-tobi.github.io/tobiA/)