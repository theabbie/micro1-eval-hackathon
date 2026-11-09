"""Grader validation: the reference answer passes, realistic wrong answers fail.

Run: python -m pytest -q
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "reference"))

from fhireval.engine import date_interval, solve_task  # noqa: E402
from fhireval.grader import answer_text, grade  # noqa: E402
from fhireval.prompt import build_prompt, load_tasks  # noqa: E402
from naive_variants import VARIANTS, solve_with  # noqa: E402

TASKS = load_tasks(ROOT / "tasks")
IDS = [t["id"] for t in TASKS]


def _sorted(e):
    return {k: sorted(v) for k, v in e.items()} if isinstance(e, dict) else sorted(e)


def _hand(task):
    return {q["id"]: _sorted(q["expected"]) for q in task["queries"]}


# ------------------------------------------------ reference solution

@pytest.mark.parametrize("task", TASKS, ids=IDS)
def test_engine_agrees_with_hand_written_answers(task):
    # Two independent derivations of every expected answer must agree.
    assert solve_task(task) == _hand(task)


@pytest.mark.parametrize("task", TASKS, ids=IDS)
def test_reference_answer_passes(task):
    g = grade(task, "Some reasoning first.\n\n" + answer_text(solve_task(task)))
    assert g["passed"] and g["score"] == 1.0


def test_committed_expected_answers_are_current():
    committed = json.loads((ROOT / "reference" / "expected_answers.json").read_text())
    assert committed == {t["id"]: solve_task(t) for t in TASKS}


# ------------------------------------------------ format leniency (no false fails)

@pytest.mark.parametrize("task", TASKS, ids=IDS)
def test_bare_ids_unsorted_duplicates_accepted(task):
    bare = lambda refs: [r.split("/")[1] for r in reversed(refs)] * 2  # noqa: E731
    ans = {qid: ({k: bare(v) for k, v in refs.items()} if isinstance(refs, dict) else bare(refs))
           for qid, refs in solve_task(task).items()}
    assert grade(task, answer_text(ans))["passed"]


def test_last_json_block_wins_and_unfenced_json_parses():
    task = TASKS[0]
    good = solve_task(task)
    wrong = {k: [] for k in good}
    assert grade(task, answer_text(wrong) + "\nCorrection:\n" + answer_text(good))["passed"]
    assert grade(task, "Final answer: " + json.dumps(good))["passed"]


# ------------------------------------------------ wrong answers fail (no false passes)

@pytest.mark.parametrize("task", TASKS, ids=IDS)
def test_every_single_resource_flip_fails(task):
    ref = solve_task(task)
    all_refs = [f"{r['resourceType']}/{r['id']}" for r in task["resources"]]
    for qid, refs in ref.items():
        slots = list(refs) if isinstance(refs, dict) else [None]
        for slot in slots:
            for r in all_refs:
                flipped = dict(ref)
                if slot is None:
                    flipped[qid] = sorted(set(refs) ^ {r})
                else:
                    flipped[qid] = dict(refs, **{slot: sorted(set(refs[slot]) ^ {r})})
                g = grade(task, answer_text(flipped))
                assert not g["passed"] and not g["queries"][qid]["correct"]


@pytest.mark.parametrize("task", TASKS, ids=IDS)
def test_list_everything_and_empty_and_garbage_fail(task):
    everything = {q["id"]: [f"{r['resourceType']}/{r['id']}" for r in task["resources"]] for q in task["queries"]}
    assert not grade(task, answer_text(everything))["passed"]
    assert not grade(task, answer_text({q["id"]: [] for q in task["queries"]}))["passed"]
    g = grade(task, "I cannot determine this.")
    assert not g["parsed"] and g["score"] == 0


def test_include_answer_as_flat_list_is_wrong():
    task = next(t for t in TASKS if t["id"] == "T11")
    ans = solve_task(task)
    ans["q5"] = ans["q5"]["match"] + ans["q5"]["include"]
    assert not grade(task, answer_text(ans))["queries"]["q5"]["correct"]


def test_missing_query_key_is_wrong():
    task = TASKS[0]
    ans = solve_task(task)
    ans.pop("q1")
    g = grade(task, answer_text(ans))
    assert not g["passed"] and not g["queries"]["q1"]["correct"]


@pytest.mark.parametrize("variant", sorted(VARIANTS))
def test_each_naive_engine_fails_somewhere(variant):
    failed = [t["id"] for t in TASKS if not grade(t, answer_text(solve_with(variant, t)))["passed"]]
    assert failed, f"{variant} passes every task; the tasks do not discriminate it"


# ------------------------------------------------ hygiene

@pytest.mark.parametrize("task", TASKS, ids=IDS)
def test_prompt_leaks_no_answers(task):
    p = build_prompt(task)
    for q in task["queries"]:
        assert q["rationale"] not in p
    assert task["why_hard"] not in p
    assert "expected" not in p and "traps" not in p


def test_dst_day_lengths():
    ny = "America/New_York"
    fall = date_interval("2024-11-03", ny)
    spring = date_interval("2024-03-10", ny)
    assert fall.hi - fall.lo == 25 * 3600
    assert spring.hi - spring.lo == 23 * 3600
