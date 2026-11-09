# FHIR Search Semantics Eval: "Which records does this query actually return?"

## Short description

Domain: healthcare interoperability (HL7 FHIR R4 REST search). The eval gives a model a small
synthetic FHIR server (10-17 resources, a stated time zone) and realistic searches from quality
measures, registries, medication reconciliation and patient lookup, and asks exactly which
resources each search returns: 11 tasks, 74 queries, graded by exact set match against a
reference FHIR search engine. Five models were run, 3 trials per task. The best models (GPT-6.1-sol,
Claude Opus 5.5) pass 88-91% of task trials, but none passes every task every time
(pass^3 at most 91%; Sonnet 5.5 64%, Haiku 5.5 36%, GPT-5.6-luna 0%). The key finding is that the
frontier failures are not about knowing FHIR or doing time-zone arithmetic. They come from
**surface priors overriding a rule the model has just stated correctly**: a normal 120/80 blood
pressure dropped from a query that, by the model's own reasoning, matches it; "Steve" judged not to
contain "eve"; an onset the model itself converts to Dec 31 2019 left out of the 2019 query.
These errors repeat across trials and do not go away at high reasoning effort.

**Video walkthrough:** <https://www.youtube.com/watch?v=297lWzlQT-c> (3:50, public)

## Domain and expertise

Healthcare interoperability: HL7 FHIR R4 REST search, as used by EHR integrations,
quality-measure engines, registries, prior-authorization services and patient-matching
tools. The tasks draw on what a FHIR integration engineer has to know to predict what a
search returns on real clinical data:

* date search is **interval** logic (the precision of both the search value and the stored
  value defines a range; `eq` means *contained*, `ge`+`le` means *overlaps*);
* offset-less and date-only values are in the **server's local time zone**, so the local day
  can be 23 or 25 hours long and UTC instants near midnight belong to the previous day;
* `Period` bounds at day precision cover the whole end day; missing bounds are unbounded;
* quantity `eq` uses the **implicit range** of the number as written; comparisons are exact;
  units are never converted;
* token syntax (`system|code`, `code`, `|code`), `:not` including resources with no value,
  `:missing`, case-sensitive codes, no subsumption;
* default string search is case/accent-insensitive **starts-with** over every name;
* separate parameters on repeating elements (BP components) and separate `_has` / chains
  are evaluated **independently**; composite parameters bind values to the same element;
* `_include` / `_revinclude` add unfiltered resources once and silently skip dangling references.

## What it tests and why it matters

Given a small FHIR server (10-17 synthetic resources), its time zone, and 5-11 real-looking
search requests, the model must return exactly the resources the server returns. Every
answer is a set of resource references, so grading is deterministic.

Who relies on this: engineers writing or reviewing FHIR queries and server code, and
increasingly AI agents and copilots that query patient records over FHIR on a clinician's
behalf. A wrong prediction is not cosmetic:

* a quality measure that drops an HbA1c drawn at 22:00 on Dec 31 (stored as a UTC instant on
  Jan 1) misreports diabetes control and can cost the practice measure credit;
* a hypertension registry that combines `component-code` and `component-value-quantity`
  flags every patient whose *systolic* is over 90 as "diastolic >= 90";
* an outreach list built from two independent `_has` clauses includes patients whose HbA1c
  is normal but who had some other result above the threshold;
* a medication reconciliation that treats `effective=2024-06-15` as "active that day" hides
  every chronic medication from the visit.

## Task overview

| Task | Scenario (server tz) | Resources / queries | Why it is hard |
|---|---|---|---|
| T01 | HbA1c measurement-year lookback (New York) | 12 / 5 | UTC instants around Dec 31/Jan 1, year-only value, local system reusing a LOINC code, `\|code`, status filter vs none, `gt9` on 9.0, `8.0` = [7.95, 8.05) |
| T02 | Labs on the DST fall-back day 2024-11-03 (New York) | 13 / 6 | 25-hour local day, repeated 01:00 hour (-04:00 then -05:00), +05:30 offset, minute-precision search values |
| T03 | Medication reconciliation for a visit day (New York) | 12 / 8 | Period end at day precision, open start/end, `eq` vs overlap, `sa`/`eb`, `:missing`, minute-precision `eq` contains almost nothing |
| T04 | Immunization history for a school form (Chicago) | 10 / 6 | `occurrenceString` not indexed (even "2019"), year/month values vs `eq`/`ne`, UTC instants into the previous local year |
| T05 | Problem-list onset for risk adjustment (Los Angeles) | 11 / 5 | `onsetAge`/`onsetString` not indexed, `recurrence` is not `active`, `:not` includes no-status, case-sensitive local code |
| T06 | Encounters in a billing month (New York) | 10 / 6 | Month containment vs overlap, ongoing encounter, backfilled end-only period, boundary instants |
| T07 | Weight-based dosing thresholds (New York) | 10 / 6 | Quantity implicit ranges (`100` vs `100.0`), `\|\|kg` matching unit text, pounds not converted, exact `gt` |
| T08 | Monthly eGFR windows across leap day and DST start (New York) | 16 / 7 | Offsets from -12:00 to +14:00 incl. +05:45/-03:30, month bounds with different offsets at each end, second-precision boundary values |
| T09 | Hypertension registry (New York) | 11 / 7 | Independent `component-*` params vs `component-code-value-quantity`, `code-value-quantity` vs components, `value-quantity` ignores components |
| T10 | Patient lookup by name and MRN (fictional people) | 10 / 11 | Accent-insensitive starts-with, old names, family-name parts, `:contains`/`:exact`, identifier system/value/`:of-type` |
| T11 | Diabetes outreach registry | 17 / 7 | `_has` independence, chain independence, composite inside `_has`, `_include` with a dangling reference, `_revinclude` scope |

Each task file (`tasks/T*.json`) contains the scenario, the resources, and for every query
the expected answer, a rationale that cites the rule that decides each borderline resource,
and per-resource "trap" tags used for failure analysis. Only the scenario, time zone,
resources and query strings are shown to the model (`fhireval/prompt.py`;
`tests/test_grader.py::test_prompt_leaks_no_answers`).

### What the model is told

The prompt says the server implements FHIR R4 search as specified
(<http://hl7.org/fhir/R4/search.html>), lists the search parameters with their types and
paths, and states the server's choice on each point the specification leaves open or
contradicts (`SERVER_CHOICES` in `fhireval/prompt.py`): local time zone for offset-less values;
"range above/below" starting at the end/start of the search value's range; `:not` including
missing values; only date-typed values indexed; no unit conversion or subsumption;
case-sensitive codes; exact comparison for number prefixes; how `name` covers HumanName parts.
Everything else is standard FHIR R4 that a practitioner is expected to know.

An ablation prompt (`--profile rules`) additionally spells out every rule in plain language.

## Grading

Code-based and deterministic (`fhireval/grader.py`):

* The answer is the last ```json block in the reply (fallback: last JSON object).
* A query is correct iff the set of returned references equals the expected set exactly.
  For `_include`/`_revinclude` queries both the `match` and `include` sets must be equal.
* **Task score** = fraction of its queries correct (partial credit). **Task pass** = all correct.
* Format leniency so correct answers are never failed on a technicality: bare ids are
  accepted, order and duplicates are ignored, earlier JSON drafts in the reply are ignored.

### How the grader and reference answers were validated (`python -m pytest -q`, 79 tests)

* **Two independent derivations of every expected answer.** The author's hand-written
  expected answer for each of the 74 queries must equal the output of the reference engine
  (`fhireval/engine.py`, a small FHIR search implementation). Disagreements during
  development were resolved by re-reading the spec and are recorded in the rationale fields.
* **Reference solution passes:** the engine's answers score 1.00 on every task
  (`python run_eval.py --oracle`).
* **Every single-resource error fails:** for every query, adding or removing any one resource
  makes the query and the task fail (no false passes from near-misses).
* **Gaming fails:** returning every resource, returning nothing, unparseable output, a missing
  query key, and an `_include` answer flattened into a list all fail.
* **Realistic wrong engines fail:** eight plausible-but-wrong implementations
  (`reference/naive_variants.py`: offset-less values as UTC, fixed offset without DST, `eq`
  as overlap, literal "range above", targets as points, exact quantity `eq`, case/accent-sensitive
  strings, no family-name parts) each fail at least one task.
* **Transcripts were read** and two grader-side ambiguities found that way were fixed before
  the main run (see "Development log").

## How to run

Requires Python >= 3.10. **One command** (no API keys needed; under a minute):

```bash
bash reproduce.sh                  # venv + deps, 79 validation tests, oracle, recorded results table
RUN_MODELS=1 bash reproduce.sh     # additionally re-runs the models via the APIs (keys from the environment)
```

The same steps by hand:

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q                       # grader + reference validation, no API calls, <1 s
python run_eval.py --oracle               # reference solution through the grader

# API backends (keys from the environment; see .env.example)
export ANTHROPIC_API_KEY=...  OPENAI_API_KEY=...
python run_eval.py --backend anthropic-api --models claude-opus-5-5 claude-sonnet-5-5 claude-haiku-5-5 \
       --trials 3 --effort medium --run myrun
python run_eval.py --backend openai-api --models gpt-6.1-sol gpt-5.6-luna --trials 3 --effort medium --run myrun
python analyze.py --run myrun             # writes results/runs/myrun/summary.md
```

`--backend claude-cli` and `--backend codex-cli` run the same prompts through the Claude
Code and Codex command-line tools instead of the APIs (this is how the recorded run below was
produced; see "Models tested"). Re-running with the same `--run` resumes and skips finished trials.

**Runtime and cost.** `pytest` and `--oracle`: under 1 s, no cost. One full matrix (11 tasks x 3
trials x 5 models = 165 single-turn calls, prompts of about 3-4k tokens) took 14 minutes of wall
time with 10 concurrent calls (median 32-51 s per call). Claude cost via the Claude Code CLI, as
reported by the CLI, for 33 trials: Opus 5.5 $2.41, Sonnet 5.5 $1.19, Haiku 5.5 $0.13. The GPT
models ran through the Codex CLI on a subscription, so the CLI reports tokens but no price (about
0.5M input and 22k output tokens for GPT-6.1-sol over 33 trials). Use those token counts with
current API prices to estimate the cost of an API run.

## Models tested and results

Run `main-v2-20261030`, 2026-10-30, FHIR prompt profile `spec` (the headline setting). Every model
got the same 11 tasks, the same prompt and the same grader. Each trial is a fresh single-turn call
with no tools. Reasoning effort was `medium` for all models. Temperature is not exposed by either CLI,
so the vendor defaults were used.

| Model (version, settings) | Trials per task | Task pass rate | pass@3 | pass^3 | Query accuracy | Mean task score (partial credit) | Cost per full run (33 trials) |
|---|---|---|---|---|---|---|---|
| `gpt-6.1-sol` (Codex CLI 0.166.0, effort medium) | 3 | 91% | 91% | 91% | 98.6% | 0.98 | subscription; 0.50M in / 22k out tokens |
| `claude-opus-5-5` (Claude Code 2.1.309, effort medium) | 3 | 88% | 100% | 82% | 98.2% | 0.99 | $2.41 |
| `claude-sonnet-5-5` (Claude Code 2.1.309, effort medium) | 3 | 85% | 100% | 64% | 97.3% | 0.97 | $1.19 |
| `claude-haiku-5-5` (Claude Code 2.1.309, effort medium) | 3 | 67% | 91% | 36% | 92.8% | 0.92 | $0.13 |
| `gpt-5.6-luna` (Codex CLI 0.166.0, effort medium) | 3 | 9% | 27% | 0% | 60.8% | 0.59 | subscription; 0.37M in / 68k out tokens |

*Task pass rate* = trials in which every query of the task was right. *pass@3* = tasks solved at least
once in 3 trials. *pass^3* = tasks solved in all 3 trials (consistency, which is what a production
integration needs). Full table, task x model matrix, failure attribution and raw replies:
[`results/runs/main-v2-20261030/summary.md`](results/runs/main-v2-20261030/summary.md), [`results/runs/main-v2-20261030/trials.jsonl`](results/runs/main-v2-20261030/trials.jsonl), [`transcripts/main-v2-20261030/`](transcripts/main-v2-20261030/).

**Task x model (trials passed out of 3)**

| Task | GPT-6.1-sol | Opus 5.5 | Sonnet 5.5 | Haiku 5.5 | GPT-5.6-luna |
|---|---|---|---|---|---|
| T01 HbA1c measurement year | 3 | 3 | 3 | 2 | 1 |
| T02 DST fall-back day | 3 | 3 | 3 | 1 | 0 |
| T03 Medication reconciliation | 3 | 3 | 3 | 2 | 0 |
| T04 Immunization history | 3 | 3 | 2 | 2 | 0 |
| T05 Problem-list onset | **0** | 3 | 1 | 3 | 0 |
| T06 Encounters in a month | 3 | 3 | 3 | 2 | 0 |
| T07 Quantity precision | 3 | 3 | 3 | **0** | 0 |
| T08 Leap day + DST month windows | 3 | 3 | 2 | 3 | 0 |
| T09 BP component vs composite | 3 | **1** | 2 | 3 | 1 |
| T10 Patient name/identifier | 3 | **1** | 3 | 3 | 0 |
| T11 _has / chains / includes | 3 | 3 | 3 | 1 | 1 |

**Ablations** (same tasks and grader):

| Setting | Model | Trials | Task pass rate | pass^k | Query accuracy | Compared with headline |
|---|---|---|---|---|---|---|
| `rules` profile (every rule spelled out) | Haiku 5.5 | 22 (2/task) | 82% | 73% | 95.9% | 67% / 36% / 92.8% |
| `rules` profile | GPT-5.6-luna | 22 (2/task) | 32% | 9% | 76.4% | 9% / 0% / 60.8% |
| effort `high`, T09+T10 only | Opus 5.5 | 6 (3/task) | 33% | 0% | 92.6% | same two errors as at `medium` |

Runs: [`results/runs/ablation-rules-20261030`](results/runs/ablation-rules-20261030),
[`results/runs/ablation-effort-high-20261030`](results/runs/ablation-effort-high-20261030).

**Transport note.** The recorded runs used the vendors' CLIs as transport (no API keys were
available during the build): `claude -p` with all tools disabled, settings and CLAUDE.md
discovery off, our own system prompt, and an empty working directory; `codex exec` with shell,
exec, apps and web search disabled, a throwaway config home and an empty directory. Codex's own
agent instructions are still present, and an organization-managed policy note (about not sharing
sensitive data) was present in the Claude context. Claude replies often ended with a one-line
reminder derived from that note. In the submitted files each such line is replaced by
`[organization policy reminder removed]` (`package.py`). The script asserts that no redacted line
contains answer content and that every trial's grade is unchanged; affected trials carry a
`redacted_policy_reminder_lines` count. No model made a tool call in any trial
(`transport.item_types` in `trials.jsonl`). The `anthropic-api` and `openai-api` backends send
the same prompt and system prompt directly to the APIs, so judges can reproduce without the CLIs.
Scores through the APIs may differ slightly. The API backends were checked offline only: both
SDKs accept the requests, but no live API call was made, and the GPT model names are the ones the
Codex CLI lists, so they may need adjusting for the OpenAI API.

## Failure analysis

Notes per task. Every failure listed was read in the transcript. "Wrong" means a resource the
model included that the server does not return (+) or omitted (-).

* **T01 (HbA1c).** Haiku once returned the year-only result for `date=2024-12-31` (+a1c-09: a year
  is not contained in a day). Luna treated `eq` as overlap and missed the local-day conversion of
  UTC instants. Frontier models solved it every time. Transcript: [transcripts/main-v2-20261030/claude-haiku-5-5/T01_t3.md](transcripts/main-v2-20261030/claude-haiku-5-5/T01_t3.md).
* **T02 (DST fall-back), close call for Haiku.** Haiku got the 25-hour day right but in one trial
  treated the month value and the collection period as "inside" every window (+k-10, +k-11 for `sa`,
  `eb` and minute `eq`), [transcripts/main-v2-20261030/claude-haiku-5-5/T02_t2.md](transcripts/main-v2-20261030/claude-haiku-5-5/T02_t2.md).
* **T03 (medication reconciliation).** Haiku dropped acetaminophen taken at 22:00 EDT (stored
  as 02:00Z the next day) from the visit day. Luna read `effective=2024-06-15` as "active that day",
  the exact bug that hides chronic medications. Transcript: [transcripts/main-v2-20261030/claude-haiku-5-5/T03_t1.md](transcripts/main-v2-20261030/claude-haiku-5-5/T03_t1.md).
* **T04 (immunizations).** Sonnet and Haiku each once omitted a year-only MMR (`2019`) from
  `date=gt2019-05-14`. A year extends past May 14, so it matches. Transcript: [transcripts/main-v2-20261030/claude-sonnet-5-5/T04_t2.md](transcripts/main-v2-20261030/claude-sonnet-5-5/T04_t2.md).
* **T05 (problem list), GPT-6.1-sol 0/3.** In all three trials GPT-6.1-sol writes in q1 that
  c-07 (`2020-01-01T07:30:00Z`) "is December 31 at 23:30 local time", then leaves it out of
  `onset-date=2019` in q5 ([transcripts/main-v2-20261030/gpt-6.1-sol/T05_t1.md](transcripts/main-v2-20261030/gpt-6.1-sol/T05_t1.md)). It derives the
  right fact and does not reuse it; the 2020 stamp wins. Sonnet twice missed an onset Period
  (Oct 2019 to Feb 2020) for `lt2020-01-01`, though part of it is before the cutoff.
* **T06 (encounters).** Haiku once treated `date=2024-07` as overlap (+5 encounters that cross the
  month boundary). Transcript: [transcripts/main-v2-20261030/claude-haiku-5-5/T06_t1.md](transcripts/main-v2-20261030/claude-haiku-5-5/T06_t1.md).
* **T07 (quantity precision), Haiku 0/3.** Haiku consistently missed `||kg` matching on
  `Quantity.unit` when the Quantity has no system or code (-w-08). The spec says the bare unit
  is matched against code or unit text. Transcript: [transcripts/main-v2-20261030/claude-haiku-5-5/T07_t1.md](transcripts/main-v2-20261030/claude-haiku-5-5/T07_t1.md).
* **T08 (leap day and DST month).** Solved by every frontier model except one Sonnet trial, which
  put values that span the boundary (a period from Feb 26 to Mar 4, the year 2024, an open-ended
  period) wholly before March 1 (`eb`) or wholly after March 31 (`sa`).
  Time-zone arithmetic with unusual offsets is not where frontier models fail. Transcript: [transcripts/main-v2-20261030/claude-sonnet-5-5/T08_t2.md](transcripts/main-v2-20261030/claude-sonnet-5-5/T08_t2.md).
* **T09 (blood pressure), Opus 1/3.** Opus explains correctly that `component-code` and
  `component-value-quantity` are independent, and that any panel with a diastolic code and any
  component >= 90 matches. It then lists "bp-03 does not match (120/80)", although 120 >= 90
  ([transcripts/main-v2-20261030/claude-opus-5-5/T09_t1.md](transcripts/main-v2-20261030/claude-opus-5-5/T09_t1.md)). In another trial it also dropped
  135/88 and 139.6/89.6 ([transcripts/main-v2-20261030/claude-opus-5-5/T09_t3.md](transcripts/main-v2-20261030/claude-opus-5-5/T09_t3.md)). Sonnet did the
  same (-bp-03, -bp-05). The dropped readings are exactly the *normal-looking* blood pressures. Haiku
  passed 3/3, so this is not a hard-reasoning gap; the clinical prior "this BP is not high" overrides
  the rule.
* **T10 (patient lookup), Opus 1/3.** Opus twice omitted "Steve" from `given:contains=eve`, while
  including "Séverine" from the same rule ([transcripts/main-v2-20261030/claude-opus-5-5/T10_t1.md](transcripts/main-v2-20261030/claude-opus-5-5/T10_t1.md)).
* **T11 (_has / includes).** Frontier models solved it every time, including the classic
  two-independent-`_has` trap. Haiku once dropped a matching Observation whose patient is not on
  the server (the match stays; only the include is skipped). Transcript: [transcripts/main-v2-20261030/claude-haiku-5-5/T11_t2.md](transcripts/main-v2-20261030/claude-haiku-5-5/T11_t2.md).
* **GPT-5.6-luna (all tasks).** It reads date `eq` as overlap and ignores Period and partial-date
  extents ("eq-means-overlap" reproduces 23 of its wrong answers exactly; see the fingerprint in
  [`results/runs/main-v2-20261030/summary.md`](results/runs/main-v2-20261030/summary.md)). With the full rule sheet it improves from 9% to 32%, so it lacks
  both the spec knowledge and the execution. Transcript: [transcripts/main-v2-20261030/gpt-5.6-luna/T04_t1.md](transcripts/main-v2-20261030/gpt-5.6-luna/T04_t1.md).

**What the numbers say**

1. *Spec knowledge separates tiers.* Haiku and Luna gain a lot when every rule is spelled out
   (Haiku 67% to 82%, Luna 9% to 32%), and the errors they make without the sheet are standard FHIR
   misconceptions (`eq` as overlap, Periods as points, no unit-text match).
2. *Frontier models know the semantics.* GPT-6.1-sol and Opus 5.5 answer 98%+ of queries correctly
   and handle DST, +14:00 offsets, composites and `_has` independence. Their remaining errors are
   rare, but they are systematic: the same resource is dropped in several trials (sol T05 3/3, Opus
   T10 2/3, T09 2/3).
3. *More reasoning does not fix them.* At `high` effort Opus makes exactly the same T09 and T10
   errors (2/3 trials each).

## Main failure mode and hot take

**Frontier models fail on FHIR search not when the rule is hard, but when the correct answer
looks wrong.** The answer the rule gives conflicts with what the data looks like: a 120/80 reading
returned by a "diastolic >= 90" query, "Steve" containing "eve", a 2020-01-01 UTC timestamp that
is 2019 locally. In each case the model states the rule correctly and then quietly overrides it.
Weaker models fail because they don't know FHIR search. The strongest models know it and are
still unreliable at exactly the boundary cases where integration bugs live, and those cases
produce the errors people don't catch, because the wrong answer looks clinically sensible.

What it would take to close the gap: models (and agents built on them) should *execute* searches
rather than predict them, or check each candidate against the rule explicitly, one resource at a
time. Evals in this area should include cases where the correct answer is counter-intuitive,
because accuracy on "normal-looking" data hides this failure.

## Development log (what changed and why)

1. **Rule-sheet prompt was too easy.** The first version gave the model a complete rule
   sheet (every prefix written as a formula). On T01-T07 all three calibration models scored
   about 100% (`results/calibration/calib-rules`). The tasks reduced to arithmetic, so the
   prompt was changed to the realistic setting: the R4 specification plus only the server's
   explicit choices. Haiku then dropped sharply and frontier models made occasional errors
   (`results/calibration/calib-spec`).
2. **Time-zone arithmetic alone is not the gap.** T08 (extreme offsets, leap day, DST month)
   was added expecting failures; Opus and GPT-6.1-sol both passed 2/2. It is kept as a hard
   but solved task (it shows the limitation is not date arithmetic).
3. **New tasks on less-known semantics** (T09-T11: composite vs independent parameters,
   string search, `_has`, includes), designed from known real-world integration bugs, not
   from model failures.
4. **Two grader ambiguities found by reading transcripts and fixed before the main run:**
   (a) Claude models matched diastolic 89.6 to `ge90` using the decimal *range* reading in the
   R4 prefix table, which contradicts the R4 number section ("implicit precision ... ignored"
   for comparison prefixes). This is a real inconsistency in the spec, so the server's choice
   (exact comparison) is now stated in the prompt. (b) Whether family-name part matching
   applies to `:exact` was not stated; it now is.
5. **A third ambiguity found in the first full run, which was then discarded and re-run.**
   In run v1 (`results/calibration/main-v1-superseded`) Sonnet 5.5 failed T01 0/3 because it gave
   the *stored* value 7.95 its own implicit range [7.945, 7.955), which is a defensible reading of
   the R4 prefix table ("searches are always performed on values that are implicitly or
   explicitly a range"). The prompt now states that stored numbers are exact points. Because this
   changed the prompt for every task, the whole matrix was re-run (`main-v2-20261030`); Sonnet's
   T01 and T07 failures disappeared. The same review found that the "tool attempts" counter for
   Codex was counting two startup warnings per run, not model actions; it was fixed.
   Calibration runs and v1 are kept for transparency but are not reported as results.

## Prior work and sources

* Built during the hackathon (Oct 30 - Nov 8, 2026). No pre-existing code or tasks.
* Specification: HL7 FHIR R4 search, <http://hl7.org/fhir/R4/search.html> (FHIR is published
  under CC0). Codes: LOINC, SNOMED CT, RxNorm, CVX and HL7 code systems are referenced by
  code only, as in any FHIR resource; no terminology content is redistributed.
* All resources, patients, names and identifiers are synthetic and fictional. No employer,
  client or patient data was used.
* Not adapted from any existing benchmark. The Harbor task layout and the participant guide's
  advice informed the structure.

## AI use

An AI coding assistant (Claude Code, model Claude Opus 5.5) was used throughout:

* It drafted the reference engine, the grader, the harness, the tests and this README, and
  proposed task data for each scenario.
* For every query, the expected answer was written by hand from the rules and then checked
  against the engine. All 74 agree (`test_engine_agrees_with_hand_written_answers`).
* Two task-side ambiguities were found by reading model transcripts and fixed before the
  reported run (see the Development log).

## Repository layout

```
README.md            this file
reproduce.sh         one-command setup, validation and (optionally) model re-run
run_eval.py          harness: tasks x models x trials, transcripts, resume
analyze.py           summary table, pass^k, task matrix, failure attribution
fhireval/engine.py   reference FHIR search engine (the reference solution)
fhireval/prompt.py   prompt builder (spec profile + server choices; rules ablation)
fhireval/grader.py   deterministic grader
fhireval/backends.py anthropic-api, openai-api, claude-cli, codex-cli
tasks/               11 task files (resources, queries, expected answers, rationales, traps)
reference/           solve.py, expected_answers.json, naive_variants.py (wrong engines)
tests/               grader and reference validation (pytest)
package.py           builds the submission zip (redaction + grade-equality + leak checks)
results/runs/        recorded run: trials.jsonl (raw replies), summary.md/json, logs
results/calibration/ development runs (not headline results)
transcripts/         one markdown transcript per trial (prompt, reply, per-query grade)
requirements.txt, .env.example
```
