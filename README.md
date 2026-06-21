# ai-sentinel-feed

A data pipeline that continuously collects, normalizes, and exposes documented AI failures, vulnerabilities, and adversarial incidents from public sources — structured for analysis, search, and downstream ML use.

---

## What this is

AI incident data is scattered. Vulnerability databases, academic trackers, and adversarial ML research each capture a different slice of the same problem space. `ai-sentinel-feed` pulls from all of them, normalizes records against a shared schema mapped to the [MITRE ATLAS](https://atlas.mitre.org/) adversarial ML taxonomy, and surfaces the unified dataset through a live API, an interactive dashboard, and versioned data dumps.

This is a living feed, not a one-time scrape. New records are ingested on a schedule; each export is timestamped.

---

## Data Sources

### Round 1 (Live)


| Source                                                     | Type             | What it contributes                                                                                       |
| ---------------------------------------------------------- | ---------------- | --------------------------------------------------------------------------------------------------------- |
| [NVD / CVE](https://nvd.nist.gov/developers)               | REST API         | AI/ML library CVEs (`pytorch`, `tensorflow`, `langchain`, `huggingface`) with CVSS severity scores        |
| [AI Incident Database (AIID)](https://incidentdatabase.ai) | GraphQL API      | Documented real-world AI failures and harms, structured by involved system and harm type                  |
| [AIAAIC](https://www.aiaaic.org)                           | CSV export       | Media-documented AI controversies and algorithmic harms — catches incidents outside technical DBs         |
| [MITRE ATLAS](https://github.com/mitre-atlas/atlas-data)   | YAML (versioned) | Adversarial ML tactic and technique taxonomy — used as the shared classification layer across all sources |




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
- `severity` normalizes CVSS scores (NVD) and qualitative harm ratings (AIID/AIAAIC) onto a shared five-point scale. Mapping logic is documented in `[docs/severity_normalization.md](docs/severity_normalization.md)`.
- `raw` stores the untouched source payload. Schema changes re-normalize from raw — no re-scraping required.

---

## Storage

```
Raw layer     →   data/raw/{source}/YYYY-MM-DD.jsonl   (untouched source output)
Structured    →   PostgreSQL                            (normalized records, queried by API + dashboard)
Exports       →   data/exports/                         (versioned data dumps, see below)
```

---

## Outputs

### API

FastAPI. Base URL: `http://localhost:8000`

```
GET /incidents                  # paginated list; filter by source, vendor, severity, date
GET /incidents/{id}             # single record
GET /incidents/stats            # counts by vendor, technique, severity over time
GET /feed                       # latest 50 records — live feed endpoint
GET /atlas/techniques           # ATLAS technique frequency across all incidents
```

Docs available at `/docs` (Swagger) and `/redoc`.

### Dashboard

Streamlit. Run locally at `http://localhost:8501`

Planned views:

- Incident volume over time, by source
- Vendor heatmap — who appears most and in which ATLAS tactics
- ATLAS technique frequency — what attack types are trending
- Severity distribution across vendors
- Searchable incident table with filter controls

### Data Dumps

Updated nightly. Available in `data/exports/`:

```
incidents.jsonl                  # all normalized records, one per line
incidents_atlas_mapped.jsonl     # records with confirmed ATLAS technique mapping only
jailbreaks.jsonl                 # jailbreak-tagged records, separate schema
```

Standard `.jsonl` format for direct use in ML training pipelines.

---

## Project Structure

```
ai-sentinel-feed/
├── sentinel/
│   ├── sources/
│   │   ├── nvd.py
│   │   ├── aiid.py
│   │   ├── aiaaic.py
│   │   └── atlas.py
│   ├── pipeline/
│   │   ├── ingest.py
│   │   ├── normalize.py
│   │   ├── deduplicate.py
│   │   └── store.py
│   ├── api/
│   │   └── main.py
│   ├── dashboard/
│   │   └── app.py
│   └── models.py
├── data/
│   ├── raw/
│   ├── exports/
│   └── atlas/
├── docs/
│   └── severity_normalization.md
├── tests/
├── .env.example
├── docker-compose.yml
└── README.md
```

---

## Setup

```bash
git clone https://github.com/tobiadeyefa/ai-sentinel-feed
cd ai-sentinel-feed
cp .env.example .env          # add NVD API key
pip install -r requirements.txt
docker-compose up -d          # starts Postgres
python -m sentinel.pipeline.ingest
```

**Environment variables:**

```
NVD_API_KEY=
AIID_GRAPHQL_URL=https://incidentdatabase.ai/api/graphql
DATABASE_URL=postgresql://...
```

---

## Status


| Source        | Status         |
| ------------- | -------------- |
| NVD / CVE     | 🔲 In progress |
| AIID          | 🔲 In progress |
| AIAAIC        | 🔲 In progress |
| MITRE ATLAS   | 🔲 In progress |
| GitHub Issues | ⬜ Planned      |
| ArXiv         | ⬜ Planned      |
| News / RSS    | ⬜ Planned      |



---

## What the data shows

*This section will be updated as the pipeline runs and patterns emerge.*

---

## Author

**Oluwatobi Adeyefa**
[tobi.adeyefa@nyu.edu](mailto:tobi.adeyefa@nyu.edu) · [LinkedIn](https://linkedin.com/in/tobiadeyefa) · [GitHub](https://github.com/tobiadeyefa)