# Round 1 Source Exploration

Notes from Initial Phase API/feed exploration.

---

## NVD / CVE

**Endpoint:** `GET https://services.nvd.nist.gov/rest/json/cves/2.0`

**Auth:** Optional `apiKey` header (recommended)

**Query strategy:** `keywordSearch` for ML stack terms: `pytorch`, `tensorflow`, `langchain`, `huggingface`.

**Sample files:** `data/raw/nvd/sample_{keyword}.json`

### Key response shape

```
vulnerabilities[].cve
  ├── id                    → source_id (e.g. CVE-2021-43811)
  ├── published             → incident_date
  ├── descriptions[].value  → description (lang=en)
  ├── metrics.cvssMetricV31[].cvssData
  │     ├── baseScore       → severity (normalize via CVSS)
  │     └── baseSeverity    → HIGH / MEDIUM / …
  ├── configurations[].nodes[].cpeMatch[].criteria  → vendor/product hints
  └── references[].url      → url
```

### Normalization notes


| My field          | NVD source                                                          |
| ----------------- | ------------------------------------------------------------------- |
| `source`          | `"NVD"`                                                             |
| `source_id`       | `cve.id`                                                            |
| `title`           | `cve.id` + short product from CPE or first line of description      |
| `description`     | `descriptions[lang=en].value`                                       |
| `incident_date`   | `published` (date part)                                             |
| `vendor`          | Parse from `affected[].affectedData[].vendor` or CPE                |
| `system`          | `affected[].affectedData[].product`                                 |
| `severity`        | Map `metrics.cvssMetricV31[0].cvssData.baseScore`                   |
| `atlas_technique` | Usually `unmapped` for library CVEs, manual/heuristic mapping later |
| `tags`            | Keyword used + CWE IDs from `weaknesses`                            |
| `url`             | `https://nvd.nist.gov/vuln/detail/{cve.id}`                         |
| `raw`             | Full CVE object                                                     |


---

## AI Incident Database (AIID)

**Endpoint:** `POST https://incidentdatabase.ai/api/graphql`

**Auth:** No API key, but **browser session required**. Direct `curl`/httpx returns `403 Forbidden - Invalid origin`. Use Playwright (headless Chromium) to load the site, then `fetch('/api/graphql')` from the page context.

**Sample file:** `data/raw/aiid/sample.json`

### Incidents vs reports

- **Incident:** canonical event (one real-world AI failure).
- **Report:** news article or submission documenting that incident. One incident → many reports.
- Ingest at the **incident** level; store linked `reports` in `raw`.

### GraphQL query

```graphql
query SampleIncidents($pagination: PaginationType) {
  incidents(pagination: $pagination) {
    incident_id
    title
    description
    date
    AllegedDeployerOfAISystem { name }
    AllegedDeveloperOfAISystem { name }
    reports {
      report_number
      title
      date_published
      source_domain
      url
    }
  }
}
```

Variables: `{ "pagination": { "limit": 50, "skip": 0 } }`

### Normalization notes


| My field          | AIID source                                                               |
| ----------------- | ------------------------------------------------------------------------- |
| `source`          | `"AIID"`                                                                  |
| `source_id`       | `incident_id` (integer as string)                                         |
| `title`           | `title`                                                                   |
| `description`     | `description`                                                             |
| `incident_date`   | `date`                                                                    |
| `vendor`          | `AllegedDeployerOfAISystem[0].name` or developer fallback                 |
| `system`          | Often embedded in title; no dedicated field                               |
| `severity`        | Qualitative mapping from harm taxonomy (TBD in severity_normalization.md) |
| `atlas_technique` | Map from AIID taxonomies / keyword heuristics                             |
| `tags`            | Derived from title/description keywords                                   |
| `url`             | `https://incidentdatabase.ai/cite/{incident_id}`                          |
| `raw`             | Full incident + nested reports                                            |


### Quirks

- `playwright` is required for reliable programmatic access (see`aiid.py`).

---

## AIAAIC

**Source:** Google Sheets CSV scraping (not a REST API).

**URL:**

```
https://docs.google.com/spreadsheets/d/1Bn55B4xz21-_Rgdr8BBb2lt0n_4rzLGxFADMlVW0PYI/export?format=csv&gid=888071280
```

**Sample file:** `data/raw/aiaaic/sample.csv` (~2,250 rows as of initial exploration)

### CSV structure (non-standard headers)


| Row | Content                            | Action          |
| --- | ---------------------------------- | --------------- |
| 0   | Merged title row (`Incidents,,,…`) | Skip            |
| 1   | Real column names                  | Use as `header` |
| 2   | Sub-header for multi-level columns | Skip            |
| 3+  | Data rows                          | Ingest          |


**pandas load:**

```python
pd.read_csv(url, header=1, skiprows=[2])
```

### Columns (19)

`AIAAIC ID#`, `Headline`, `Occurred`, `Deployer`, `Developer`, `System name`, `Technology`, `Purpose`, `News trigger (taxonomy)`, `Ethical issue (taxonomy)`, `Impacted area` (jurisdiction/sector sub-cols), `External harm (taxonomy)`, `Consequence (taxonomy)`, `Response (taxonomy)`, `Summary/links`

### Normalization notes


| My field          | AIAAIC source                                                            |
| ----------------- | ------------------------------------------------------------------------ |
| `source`          | `"AIAAIC"`                                                               |
| `source_id`       | `AIAAIC ID#` (e.g. `AIAAIC2264`)                                         |
| `title`           | `Headline`                                                               |
| `description`     | `Summary/links`                                                          |
| `incident_date`   | `Occurred` (often year only, e.g. `2026`)                                |
| `vendor`          | `Deployer` or `Developer`                                                |
| `system`          | `System name` or `Technology`                                            |
| `severity`        | Derive from `External harm (taxonomy)` / `Consequence (taxonomy)`        |
| `atlas_technique` | Heuristic from `Ethical issue (taxonomy)`                                |
| `tags`            | Taxonomy columns + `Technology`                                          |
| `url`             | Parse first link from `Summary/links` or construct from AIAAIC site slug |
| `raw`             | Full CSV row as dict                                                     |


### Quirks

- Many optional fields are sparse (`NaN` for Deployer, System name).
- License: CC BY-SA 4.0, attribute AIAAIC in exports.

---

## MITRE ATLAS

**Source:** Versioned YAML from [mitre-atlas/atlas-data](https://github.com/mitre-atlas/atlas-data)

**File:** `dist/ATLAS.yaml` (also `dist/ATLAS-latest.yaml`)

**Local copy:** `data/atlas/ATLAS.yaml` (~452 KB)

### Structure

```yaml
id: ATLAS
name: Adversarial Threat Landscape for AI Systems
version: "…"
matrices:
  - id: ATLAS
    name: ATLAS Matrix
    tactics:        # 16 tactics
      - id: AML.TA0002
        name: Reconnaissance
    techniques:     # 170 techniques
      - id: AML.T0000
        name: Search Open Technical Databases
        tactics: [AML.TA0002]
```

### Lookup pattern

1. Load `matrices[0].techniques` → build `id → technique` map.
2. Load `matrices[0].tactics` → build `id → tactic name` map.
3. For a technique, resolve `tactics[]` IDs to tactic names.

### Role in pipeline

ATLAS is the **classification layer**. Used to:

- Map incidents from other sources to `atlas_technique` / `atlas_tactic`
- Power `GET /atlas/techniques` frequency endpoint
- Flag `unmapped` records for manual review

### Quirks

- Download at ingest/setup time (YAML, gitignored).
- Technique IDs use `AML.T####` format; tactics use `AML.TA####`.
- Sub-techniques reference parent via `subtechnique-of`.

---

## Cross-source observations

1. **Date precision varies:** NVD has full timestamps; AIID has dates; AIAAIC often has year only.
2. **Vendor/system extraction is messy:** Each source uses different fields, normalization logic will be source-specific.
3. **Severity is heterogeneous:** CVSS scores (NVD) vs qualitative taxonomies (AIID/AIAAIC), needs `severity_normalization.md`.
4. **Deduplication across sources:** Same real-world event may appear in AIID and AIAAIC with different IDs, cross-source dedup is a problem to be solved on later iterations (title/date fuzzy match).

---

