"""Deterministic grader.

Parsing is lenient about format (so a correct answer is never failed on a
technicality); scoring is strict about content.

  * Answer = the LAST ```json fenced block in the reply; if none, the last
    top-level {...} that parses as JSON.
  * References may be "ResourceType/id" or a bare id (ids are unique within a
    task); whitespace and duplicates are ignored, order is ignored.
  * A query is correct iff the returned set equals the expected set exactly
    (for _include queries: both the "match" and the "include" sets).
    Listing every resource therefore fails any query whose answer is a subset.
  * Task score = fraction of queries correct (partial credit).
    Task pass  = every query correct.
"""

from __future__ import annotations

import json
import re

_FENCE = re.compile(r"```(?:json)?\s*\n(.*?)```", re.S | re.I)


def extract_answer(text: str) -> dict | None:
    for block in reversed(_FENCE.findall(text or "")):
        try:
            obj = json.loads(block)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue
    # Fallback: scan for balanced {...} candidates from the end.
    starts = [i for i, ch in enumerate(text or "") if ch == "{"]
    for s in reversed(starts):
        depth = 0
        for j in range(s, len(text)):
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(text[s : j + 1])
                        if isinstance(obj, dict):
                            return obj
                    except json.JSONDecodeError:
                        pass
                    break
    return None


def _normalise(refs, by_id: dict[str, str]) -> set[str] | None:
    if not isinstance(refs, list):
        return None
    out = set()
    for r in refs:
        if not isinstance(r, str):
            return None
        r = r.strip()
        if "/" not in r and r in by_id:
            r = by_id[r]
        out.add(r)
    return out


def _expected_sets(expected) -> dict[str, set[str]]:
    """List answers -> {"": set}; _include answers -> {"match": set, "include": set}."""
    if isinstance(expected, dict):
        return {k: set(expected[k]) for k in ("match", "include")}
    return {"": set(expected)}


def _got_sets(got, shape, by_id) -> dict[str, set[str]] | None:
    if shape == [""]:
        s = _normalise(got, by_id)
        return None if s is None else {"": s}
    if not isinstance(got, dict):
        return None
    out = {}
    for k in shape:
        s = _normalise(got.get(k, []), by_id)
        if s is None:
            return None
        out[k] = s
    return out


def grade(task: dict, reply_text: str) -> dict:
    by_id = {r["id"]: f"{r['resourceType']}/{r['id']}" for r in task["resources"]}
    answer = extract_answer(reply_text)
    per_query = {}
    for q in task["queries"]:
        exp = _expected_sets(q["expected"])
        got = _got_sets(answer.get(q["id"]), list(exp), by_id) if answer else None
        tag = lambda k, refs: sorted(f"{k}:{r}" if k else r for r in refs)  # noqa: E731
        if got is None:
            per_query[q["id"]] = {"correct": False, "parsed": False, "false_positives": [],
                                  "false_negatives": [x for k in exp for x in tag(k, exp[k])]}
            continue
        per_query[q["id"]] = {
            "correct": got == exp,
            "parsed": True,
            "false_positives": [x for k in exp for x in tag(k, got[k] - exp[k])],
            "false_negatives": [x for k in exp for x in tag(k, exp[k] - got[k])],
        }
    n_correct = sum(v["correct"] for v in per_query.values())
    return {
        "parsed": answer is not None,
        "score": n_correct / len(task["queries"]),
        "passed": n_correct == len(task["queries"]),
        "queries": per_query,
    }


def answer_text(answer: dict) -> str:
    """Render an answer dict the way a model is asked to (used for grader tests)."""
    return "```json\n" + json.dumps(answer) + "\n```"
