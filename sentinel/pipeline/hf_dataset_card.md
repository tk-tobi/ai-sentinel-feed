---
license: mit
task_categories:
  - text-classification
  - question-answering
language:
  - en
tags:
  - security
  - ai-safety
  - incidents
  - mitre-atlas
  - vulnerabilities
  - responsible-ai
size_categories:
  - 1K<n<10K
---

# ai-sentinel-feed

Unified, normalized AI incident records from public sources, mapped where possible to the [MITRE ATLAS](https://atlas.mitre.org/) adversarial ML taxonomy.

**Live API:** see the project README on GitHub (`tk-tobi/ai-sentinel-feed`).

## Dataset splits

| Split | Description |
|-------|-------------|
| `incidents` | All normalized records |
| `incidents_atlas_mapped` | Records with a mapped ATLAS technique (not `unmapped`) |
| `jailbreaks` | Records tagged heuristically for jailbreak / prompt-injection themes |

Record counts at last sync (`{{exported_at}}`):

```json
{{split_counts}}
```

Total incidents in `incidents`: **{{total_records}}**.

## Schema

Each row is a JSON object with:

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Stable SHA-256 id (`source` + `source_id`) |
| `source` | string | `NVD`, `AIID`, or `AIAAIC` |
| `source_id` | string | Upstream identifier (CVE id, AIID id, AIAAIC id) |
| `title` | string | Short headline |
| `description` | string | Normalized description (PII masked) |
| `incident_date` | date \| null | When the incident occurred |
| `ingested_at` | datetime | When this pipeline ingested the record |
| `vendor` | string \| null | Alleged deployer / vendor |
| `system` | string \| null | Product or system name |
| `atlas_technique` | string | MITRE ATLAS technique id or `unmapped` |
| `atlas_tactic` | string \| null | ATLAS tactic name |
| `severity` | string | `critical`, `high`, `medium`, `low`, `informational` |
| `tags` | list[string] | Source-specific tags |
| `url` | string \| null | Canonical reference URL |
| `raw` | object | Untouched upstream payload subset |

## Sources

- **NVD:** AI/ML library CVEs (`pytorch`, `tensorflow`, `langchain`, `huggingface`)
- **AIID:** [AI Incident Database](https://incidentdatabase.ai/)
- **AIAAIC:** [AIAAIC Repository](https://www.aiaaic.org/aiaaic-repository)

## Usage

```python
from datasets import load_dataset

ds = load_dataset("{{repo_id}}")
print(ds["incidents"][0])

# Or load a single JSONL file directly:
ds = load_dataset("json", data_files="hf://datasets/{{repo_id}}/incidents.jsonl")
```

## Citation

If you use this dataset, cite the upstream sources (NVD, AIID, AIAAIC) and link to the `ai-sentinel-feed` repository.

## License

Dataset compilation and normalization code is MIT-licensed. Upstream content remains subject to each source's terms.
