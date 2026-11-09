# Results: run `ablation-effort-high-20261030`

| Model | Backend / effort | Trials (per task) | Task pass rate | pass@k | pass^k | Query accuracy | Mean task score | Cost | Wall time |
|---|---|---|---|---|---|---|---|---|---|
| `claude-opus-5-5` | claude-cli / high | 6 (3) | 33% | 100% | 0% | 92.6% | 0.92 | $0.30 | 226s |

## Task x model (trials passed)

| Task | `claude-opus-5-5` |
|---|---|
| T01 HbA1c measurement-year lookback (quality measure) | - |
| T02 Lab results on a date of service that contains the DST fall-back | - |
| T03 Medication reconciliation for a single visit day | - |
| T04 Immunization history for a school/camp form | - |
| T05 Problem-list onset dates for a risk-adjustment review | - |
| T06 Encounters in a billing month | - |
| T07 Body-weight thresholds: quantity precision and units | - |
| T08 Monthly lookback windows across a leap day and the spring-forward DST change | - |
| T09 Hypertension registry: component vs composite blood-pressure search | 1/3 |
| T10 Patient lookup: string and identifier search semantics | 1/3 |
| T11 Diabetes outreach registry: reverse chaining, chaining and includes | - |

## Failure attribution (wrong resources by author-assigned trap tag)

- `claude-opus-5-5`: component-independence 2, string-contains 2, identifier-type 2, string-name-covers-prefix 2

## Wrong-rule fingerprint (failed queries reproduced exactly by a naive engine)

- `claude-opus-5-5`: (no single-rule variant) 4

Errors / tool attempts per model: `claude-opus-5-5` 0 errors, 0 trials with blocked tool attempts
