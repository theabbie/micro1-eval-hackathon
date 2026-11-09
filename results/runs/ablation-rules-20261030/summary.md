# Results: run `ablation-rules-20261030`

| Model | Backend / effort | Trials (per task) | Task pass rate | pass@k | pass^k | Query accuracy | Mean task score | Cost | Wall time |
|---|---|---|---|---|---|---|---|---|---|
| `gpt-5.6-luna` | codex-cli / medium | 22 (2) | 32% | 55% | 9% | 76.4% | 0.76 | n/a (259,366 in / 27,941 out tok) | 854s |
| `claude-haiku-5-5` | claude-cli / medium | 22 (2) | 82% | 91% | 73% | 95.9% | 0.96 | $0.08 | 827s |

## Task x model (trials passed)

| Task | `gpt-5.6-luna` | `claude-haiku-5-5` |
|---|---|---|
| T01 HbA1c measurement-year lookback (quality measure) | 0/2 | 2/2 |
| T02 Lab results on a date of service that contains the DST fall-back | 0/2 | 0/2 |
| T03 Medication reconciliation for a single visit day | 1/2 | 2/2 |
| T04 Immunization history for a school/camp form | 0/2 | 2/2 |
| T05 Problem-list onset dates for a risk-adjustment review | 0/2 | 2/2 |
| T06 Encounters in a billing month | 1/2 | 2/2 |
| T07 Body-weight thresholds: quantity precision and units | 1/2 | 1/2 |
| T08 Monthly lookback windows across a leap day and the spring-forward DST change | 2/2 | 2/2 |
| T09 Hypertension registry: component vs composite blood-pressure search | 1/2 | 2/2 |
| T10 Patient lookup: string and identifier search semantics | 0/2 | 1/2 |
| T11 Diabetes outreach registry: reverse chaining, chaining and includes | 1/2 | 2/2 |

## Failure attribution (wrong resources by author-assigned trap tag)

- `gpt-5.6-luna`: tz-local-day-boundary 13, dst-repeated-hour 12, minute-precision-interval 9, dst-day-length 7, string-contains 5, quantity-precision-range 4, string-starts-with 4, tz-foreign-offset 3
- `claude-haiku-5-5`: dst-repeated-hour 4, minute-precision-interval 3, period-overlap 2, partial-date-interval 1, tz-foreign-offset 1, unit-no-conversion 1, quantity-unit-matching 1, string-family-parts 1

## Wrong-rule fingerprint (failed queries reproduced exactly by a naive engine)

- `gpt-5.6-luna`: (no single-rule variant) 31, offsetless-as-UTC 3, string-no-family-parts 1
- `claude-haiku-5-5`: (no single-rule variant) 5, string-no-family-parts 1

Errors / tool attempts per model: `gpt-5.6-luna` 0 errors, 0 trials with blocked tool attempts; `claude-haiku-5-5` 0 errors, 0 trials with blocked tool attempts
