# Results: run `calib-spec2`

| Model | Backend / effort | Trials (per task) | Task pass rate | pass@k | pass^k | Query accuracy | Mean task score | Cost | Wall time |
|---|---|---|---|---|---|---|---|---|---|
| `claude-opus-5-5` | claude-cli / medium | 3 (1) | 33% | 33% | 33% | 80.0% | 0.80 | $0.27 | 103s |
| `claude-haiku-5-5` | claude-cli / medium | 3 (1) | 33% | 33% | 33% | 80.0% | 0.80 | $0.01 | 110s |
| `gpt-6.1-sol` | codex-cli / medium | 3 (1) | 100% | 100% | 100% | 100.0% | 1.00 | n/a (56,795 in / 2,116 out tok) | 108s |

## Task x model (trials passed)

| Task | `claude-opus-5-5` | `claude-haiku-5-5` | `gpt-6.1-sol` |
|---|---|---|---|
| T01 HbA1c measurement-year lookback (quality measure) | - | - | - |
| T02 Lab results on a date of service that contains the DST fall-back | - | - | - |
| T03 Medication reconciliation for a single visit day | - | - | - |
| T04 Immunization history for a school/camp form | - | - | - |
| T05 Problem-list onset dates for a risk-adjustment review | - | - | - |
| T06 Encounters in a billing month | - | - | - |
| T07 Body-weight thresholds: quantity precision and units | - | - | - |
| T08 Monthly lookback windows across a leap day and the spring-forward DST change | - | - | - |
| T09 Hypertension registry: component vs composite blood-pressure search | 0/1 | 0/1 | 1/1 |
| T10 Patient lookup: string and identifier search semantics | 0/1 | 0/1 | 1/1 |
| T11 Diabetes outreach registry: reverse chaining, chaining and includes | 1/1 | 1/1 | 1/1 |

## Failure attribution (wrong resources by author-assigned trap tag)

- `claude-opus-5-5`: quantity-precision-range 3, exact-comparison-boundary 3, string-contains 1, identifier-type 1, string-name-covers-prefix 1, string-family-parts 1, identifier-system 1
- `claude-haiku-5-5`: quantity-precision-range 3, exact-comparison-boundary 3, string-family-parts 2, identifier-system 2
- `gpt-6.1-sol`: none

## Wrong-rule fingerprint (failed queries reproduced exactly by a naive engine)

- `claude-opus-5-5`: (no single-rule variant) 5
- `claude-haiku-5-5`: (no single-rule variant) 4, string-no-family-parts 1
- `gpt-6.1-sol`: none

Errors / tool attempts per model: `claude-opus-5-5` 0 errors, 0 trials with blocked tool attempts; `claude-haiku-5-5` 0 errors, 0 trials with blocked tool attempts; `gpt-6.1-sol` 0 errors, 3 trials with blocked tool attempts
