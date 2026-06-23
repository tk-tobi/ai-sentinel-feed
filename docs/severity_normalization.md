# Severity Normalization

All incident records use a shared five-point scale:


| Value           | Meaning                                                                        |
| --------------- | ------------------------------------------------------------------------------ |
| `critical`      | Severe harm, loss of life, systemic exploitation, major data breach            |
| `high`          | Significant harm, injury, wrongful arrest, discrimination, active exploitation |
| `medium`        | Moderate harm, controversy, misleading output, privacy concerns                |
| `low`           | Minor or limited harm                                                          |
| `informational` | No harm score available, or negligible impact                                  |


Implementation: `[sentinel/severity.py](../sentinel/severity.py)`

---

## NVD / CVE (CVSS)

Primary signal: **CVSS v3.1 base score** (`metrics.cvssMetricV31[].cvssData.baseScore`).

Fallback: CVSS v3.0, then textual `baseSeverity` label.


| CVSS score    | Severity        |
| ------------- | --------------- |
| 9.0 – 10.0    | `critical`      |
| 7.0 – 8.9     | `high`          |
| 4.0 – 6.9     | `medium`        |
| 0.1 – 3.9     | `low`           |
| 0.0 / missing | `informational` |


CVSS v2-only CVEs fall back to the textual label mapping:


| NVD label | Severity        |
| --------- | --------------- |
| CRITICAL  | `critical`      |
| HIGH      | `high`          |
| MEDIUM    | `medium`        |
| LOW       | `low`           |
| NONE      | `informational` |


---

## AIID (qualitative)

AIID does not ship a numeric severity score. I derived severity from `title` and `description` using keyword heuristics in `qualitative_harm_to_severity()`.


| Signal terms (examples)                                         | Severity        |
| --------------------------------------------------------------- | --------------- |
| death, fatal, killed, suicide, mass shooting, sexual violence   | `critical`      |
| injury, jail, arrest, discriminat*, leak, breach, exploit, harm | `high`          |
| controvers*, backlash, misleading, inaccurate, privacy          | `medium`        |
| (other non-empty text)                                          | `low`           |
| empty / missing                                                 | `informational` |


Future improvement: map AIID taxonomy classifications when we ingest them in Phase 4.

---

## AIAAIC (qualitative)

AIAAIC provides taxonomy columns rather than scores. Severity is derived from:

- `Headline`
- `External harm (taxonomy)`
- `Consequence (taxonomy)`
- `Summary/links`

Same `qualitative_harm_to_severity()` heuristic as AIID. Taxonomy-specific rules can be added when we have enough labeled examples to calibrate.

---

## ATLAS

MITRE ATLAS is a taxonomy source, and ATLAS techniques do not carry severity scores.

---

## Defaults

When no signal is available, severity defaults to `informational`. This keeps unmapped or sparse records in the dataset without inflating risk scores.