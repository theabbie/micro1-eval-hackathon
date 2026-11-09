# Results: run `main-v2-20261030`

| Model | Backend / effort | Trials (per task) | Task pass rate | pass@k | pass^k | Query accuracy | Mean task score | Cost | Wall time |
|---|---|---|---|---|---|---|---|---|---|
| `gpt-6.1-sol` | codex-cli / medium | 33 (3) | 91% | 91% | 91% | 98.6% | 0.98 | n/a (498,982 in / 21,984 out tok) | 1457s |
| `claude-opus-5-5` | claude-cli / medium | 33 (3) | 88% | 100% | 82% | 98.2% | 0.99 | $2.41 | 1681s |
| `claude-sonnet-5-5` | claude-cli / medium | 33 (3) | 85% | 100% | 64% | 97.3% | 0.97 | $1.19 | 1365s |
| `gpt-5.6-luna` | codex-cli / medium | 33 (3) | 9% | 27% | 0% | 60.8% | 0.59 | n/a (369,413 in / 67,791 out tok) | 1762s |
| `claude-haiku-5-5` | claude-cli / medium | 33 (3) | 67% | 91% | 36% | 92.8% | 0.92 | $0.13 | 1436s |

## Task x model (trials passed)

| Task | `gpt-6.1-sol` | `claude-opus-5-5` | `claude-sonnet-5-5` | `gpt-5.6-luna` | `claude-haiku-5-5` |
|---|---|---|---|---|---|
| T01 HbA1c measurement-year lookback (quality measure) | 3/3 | 3/3 | 3/3 | 1/3 | 2/3 |
| T02 Lab results on a date of service that contains the DST fall-back | 3/3 | 3/3 | 3/3 | 0/3 | 1/3 |
| T03 Medication reconciliation for a single visit day | 3/3 | 3/3 | 3/3 | 0/3 | 2/3 |
| T04 Immunization history for a school/camp form | 3/3 | 3/3 | 2/3 | 0/3 | 2/3 |
| T05 Problem-list onset dates for a risk-adjustment review | 0/3 | 3/3 | 1/3 | 0/3 | 3/3 |
| T06 Encounters in a billing month | 3/3 | 3/3 | 3/3 | 0/3 | 2/3 |
| T07 Body-weight thresholds: quantity precision and units | 3/3 | 3/3 | 3/3 | 0/3 | 0/3 |
| T08 Monthly lookback windows across a leap day and the spring-forward DST change | 3/3 | 3/3 | 2/3 | 0/3 | 3/3 |
| T09 Hypertension registry: component vs composite blood-pressure search | 3/3 | 1/3 | 2/3 | 1/3 | 3/3 |
| T10 Patient lookup: string and identifier search semantics | 3/3 | 1/3 | 3/3 | 0/3 | 3/3 |
| T11 Diabetes outreach registry: reverse chaining, chaining and includes | 3/3 | 3/3 | 3/3 | 1/3 | 1/3 |

## Failure attribution (wrong resources by author-assigned trap tag)

- `gpt-6.1-sol`: tz-local-day-boundary 3
- `claude-opus-5-5`: component-independence 3, string-contains 2, identifier-type 2, string-name-covers-prefix 2, quantity-precision-range 1, exact-comparison-boundary 1
- `claude-sonnet-5-5`: partial-date-interval 5, period-overlap 3, component-independence 2, period-open-end 1
- `gpt-5.6-luna`: partial-date-interval 48, period-overlap 40, period-open-end 21, dst-month-boundary 13, dst-repeated-hour 12, period-day-precision-end 12, period-open-start 12, tz-local-day-boundary 11
- `claude-haiku-5-5`: partial-date-interval 9, period-overlap 8, quantity-unit-matching 3, tz-local-day-boundary 2, period-open-end 1, period-open-start 1, dangling-reference 1, has-independence 1

## Wrong-rule fingerprint (failed queries reproduced exactly by a naive engine)

- `gpt-6.1-sol`: offsetless-as-UTC 3
- `claude-opus-5-5`: (no single-rule variant) 4
- `claude-sonnet-5-5`: (no single-rule variant) 4, targets-as-points 2
- `gpt-5.6-luna`: (no single-rule variant) 51, eq-means-overlap 23, targets-as-points 10, fixed-std-offset-no-DST 3, string-no-family-parts 1
- `claude-haiku-5-5`: (no single-rule variant) 9, eq-means-overlap 5, targets-as-points 2

Errors / tool attempts per model: `gpt-6.1-sol` 0 errors, 0 trials with blocked tool attempts; `claude-opus-5-5` 0 errors, 0 trials with blocked tool attempts; `claude-sonnet-5-5` 0 errors, 0 trials with blocked tool attempts; `gpt-5.6-luna` 0 errors, 0 trials with blocked tool attempts; `claude-haiku-5-5` 0 errors, 0 trials with blocked tool attempts
