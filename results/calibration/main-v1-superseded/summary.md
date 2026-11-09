# Results: run `main-20261030`

| Model | Backend / effort | Trials (per task) | Task pass rate | pass@k | pass^k | Query accuracy | Mean task score | Cost | Wall time |
|---|---|---|---|---|---|---|---|---|---|
| `claude-opus-5-5` | claude-cli / medium | 33 (3) | 94% | 100% | 82% | 99.1% | 0.99 | $2.58 | 1405s |
| `gpt-6.1-sol` | codex-cli / medium | 33 (3) | 97% | 100% | 91% | 99.5% | 0.99 | n/a (580,807 in / 24,106 out tok) | 1118s |
| `claude-sonnet-5-5` | claude-cli / medium | 33 (3) | 73% | 91% | 45% | 92.3% | 0.91 | $1.27 | 1236s |
| `gpt-5.6-luna` | codex-cli / medium | 33 (3) | 0% | 0% | 0% | 56.3% | 0.55 | n/a (368,443 in / 64,411 out tok) | 1951s |
| `claude-haiku-5-5` | claude-cli / medium | 33 (3) | 58% | 82% | 27% | 91.4% | 0.90 | $0.13 | 1480s |

## Task x model (trials passed)

| Task | `claude-opus-5-5` | `gpt-6.1-sol` | `claude-sonnet-5-5` | `gpt-5.6-luna` | `claude-haiku-5-5` |
|---|---|---|---|---|---|
| T01 HbA1c measurement-year lookback (quality measure) | 3/3 | 3/3 | 0/3 | 0/3 | 0/3 |
| T02 Lab results on a date of service that contains the DST fall-back | 3/3 | 3/3 | 2/3 | 0/3 | 2/3 |
| T03 Medication reconciliation for a single visit day | 3/3 | 3/3 | 2/3 | 0/3 | 2/3 |
| T04 Immunization history for a school/camp form | 3/3 | 3/3 | 3/3 | 0/3 | 3/3 |
| T05 Problem-list onset dates for a risk-adjustment review | 3/3 | 2/3 | 2/3 | 0/3 | 1/3 |
| T06 Encounters in a billing month | 3/3 | 3/3 | 3/3 | 0/3 | 1/3 |
| T07 Body-weight thresholds: quantity precision and units | 3/3 | 3/3 | 1/3 | 0/3 | 0/3 |
| T08 Monthly lookback windows across a leap day and the spring-forward DST change | 3/3 | 3/3 | 3/3 | 0/3 | 2/3 |
| T09 Hypertension registry: component vs composite blood-pressure search | 2/3 | 3/3 | 2/3 | 0/3 | 3/3 |
| T10 Patient lookup: string and identifier search semantics | 2/3 | 3/3 | 3/3 | 0/3 | 3/3 |
| T11 Diabetes outreach registry: reverse chaining, chaining and includes | 3/3 | 3/3 | 3/3 | 0/3 | 2/3 |

## Failure attribution (wrong resources by author-assigned trap tag)

- `claude-opus-5-5`: component-independence 1, string-contains 1, identifier-type 1, string-name-covers-prefix 1
- `gpt-6.1-sol`: tz-local-day-boundary 1
- `claude-sonnet-5-5`: quantity-precision-range 9, token-any-coding 3, partial-date-interval 3, tz-foreign-offset 3, sa-eb-touching-boundary 3, period-overlap 2, (untagged) 2, component-independence 1
- `gpt-5.6-luna`: partial-date-interval 53, period-overlap 43, period-open-end 27, tz-local-day-boundary 22, period-open-start 18, period-day-precision-end 15, quantity-precision-range 7, (untagged) 7
- `claude-haiku-5-5`: period-overlap 11, partial-date-interval 9, period-open-end 5, quantity-precision-range 4, period-open-start 4, period-day-precision-end 3, quantity-unit-matching 3, tz-local-day-boundary 2

## Wrong-rule fingerprint (failed queries reproduced exactly by a naive engine)

- `claude-opus-5-5`: (no single-rule variant) 2
- `gpt-6.1-sol`: offsetless-as-UTC 1
- `claude-sonnet-5-5`: (no single-rule variant) 14, fixed-std-offset-no-DST 2, targets-as-points 1
- `gpt-5.6-luna`: (no single-rule variant) 52, eq-means-overlap 30, targets-as-points 13, fixed-std-offset-no-DST 2, offsetless-as-UTC 1
- `claude-haiku-5-5`: eq-means-overlap 10, (no single-rule variant) 8, targets-as-points 3

Errors / tool attempts per model: `claude-opus-5-5` 0 errors, 0 trials with blocked tool attempts; `gpt-6.1-sol` 0 errors, 33 trials with blocked tool attempts; `claude-sonnet-5-5` 0 errors, 0 trials with blocked tool attempts; `gpt-5.6-luna` 0 errors, 33 trials with blocked tool attempts; `claude-haiku-5-5` 0 errors, 0 trials with blocked tool attempts
