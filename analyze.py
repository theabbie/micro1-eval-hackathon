#!/usr/bin/env python3
"""Summarise a run: python analyze.py --run main-20261030

Writes results/runs/<run>/summary.md and summary.json:
  * per model: trials, task pass rate, pass@k, pass^k, query accuracy, cost, runtime
  * task x model matrix (passes out of k)
  * failure attribution: every wrongly included/excluded resource is mapped to the
    trap tags the task author attached to it (tasks/*.json "traps")
  * wrong-rule fingerprint: for each failed query, which naive engine
    (reference/naive_variants.py) reproduces the model's exact wrong answer
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "reference"))

from fhireval.grader import _expected_sets, _got_sets, extract_answer, grade  # noqa: E402
from fhireval.prompt import load_tasks  # noqa: E402
from naive_variants import VARIANTS, solve_with  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    args = ap.parse_args()
    run_dir = ROOT / "results" / "runs" / args.run
    trials = [json.loads(l) for l in (run_dir / "trials.jsonl").read_text().splitlines()]
    tasks = {t["id"]: t for t in load_tasks(ROOT / "tasks")}
    for t in trials:  # always regrade the stored raw reply against the current task files
        t["grade"] = grade(tasks[t["task"]], t["text"])
    models = list(dict.fromkeys(t["model"] for t in trials))
    by = defaultdict(list)
    for t in trials:
        by[(t["model"], t["task"])].append(t)

    variant_answers = {v: {tid: solve_with(v, t) for tid, t in tasks.items()} for v in VARIANTS}

    summary = {"run": args.run, "models": {}, "matrix": {}, "traps": {}, "fingerprints": {}}
    for m in models:
        mt = [t for t in trials if t["model"] == m]
        k = max(t["trial"] for t in mt)
        n_q = sum(len(t["grade"]["queries"]) for t in mt)
        q_ok = sum(v["correct"] for t in mt for v in t["grade"]["queries"].values())
        per_task = {tid: by[(m, tid)] for tid in tasks if by[(m, tid)]}
        cost = [t["cost_usd"] for t in mt if t["cost_usd"] is not None]
        toks = [t["usage"] for t in mt if t["usage"]]
        summary["models"][m] = {
            "backend": mt[0]["backend"], "effort": mt[0]["effort"], "profile": mt[0].get("profile"),
            "resolved_model": sorted({str(t["resolved_model"]) for t in mt}),
            "trials": len(mt), "trials_per_task": k, "errors": sum(1 for t in mt if t["error"]),
            "tool_attempt_trials": sum(1 for t in mt if t["tool_attempts"]),
            "task_pass_rate": sum(t["grade"]["passed"] for t in mt) / len(mt),
            "mean_task_score": sum(t["grade"]["score"] for t in mt) / len(mt),
            "query_accuracy": q_ok / n_q,
            "pass_at_k": sum(any(t["grade"]["passed"] for t in ts) for ts in per_task.values()) / len(per_task),
            "pass_hat_k": sum(all(t["grade"]["passed"] for t in ts) and len(ts) == k
                              for ts in per_task.values()) / len(per_task),
            "cost_usd_total": round(sum(cost), 4) if cost else None,
            "output_tokens_total": sum(u.get("output_tokens", 0) for u in toks),
            "input_tokens_total": sum(u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0)
                                      + u.get("cache_read_input_tokens", 0) for u in toks),
            "seconds_total": round(sum(t["seconds"] for t in mt)),
        }
        summary["matrix"][m] = {tid: f"{sum(t['grade']['passed'] for t in ts)}/{len(ts)}"
                                for tid, ts in per_task.items()}

        trap_counts, fp = Counter(), Counter()
        for t in mt:
            traps = tasks[t["task"]]["traps"]
            for qid, v in t["grade"]["queries"].items():
                if not v["parsed"]:
                    trap_counts["(unparsed answer)"] += 1
                    continue
                for ref in v["false_positives"] + v["false_negatives"]:
                    ref = ref.split(":", 1)[1] if ref.startswith(("match:", "include:")) else ref
                    for tag in traps.get(ref, ["(untagged)"]):
                        trap_counts[tag] += 1
        summary["traps"][m] = dict(trap_counts.most_common())

        for t in mt:
            ans = extract_answer(t["text"])
            task = tasks[t["task"]]
            by_id = {r["id"]: f"{r['resourceType']}/{r['id']}" for r in task["resources"]}
            for q in task["queries"]:
                if t["grade"]["queries"][q["id"]]["correct"] or not ans:
                    continue
                exp = _expected_sets(q["expected"])
                got = _got_sets(ans.get(q["id"]), list(exp), by_id)
                hits = [v for v in VARIANTS
                        if got is not None and _expected_sets(variant_answers[v][t["task"]][q["id"]]) == got]
                for h in hits or ["(no single-rule variant)"]:
                    fp[h] += 1
        summary["fingerprints"][m] = dict(fp.most_common())

    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    md = [f"# Results: run `{args.run}`", "",
          "| Model | Backend / effort | Trials (per task) | Task pass rate | pass@k | pass^k | Query accuracy | Mean task score | Cost | Wall time |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for m, s in summary["models"].items():
        cost = f"${s['cost_usd_total']:.2f}" if s["cost_usd_total"] is not None else \
            f"n/a ({s['input_tokens_total']:,} in / {s['output_tokens_total']:,} out tok)"
        md.append(f"| `{m}` | {s['backend']} / {s['effort']} | {s['trials']} ({s['trials_per_task']}) | "
                  f"{s['task_pass_rate']:.0%} | {s['pass_at_k']:.0%} | {s['pass_hat_k']:.0%} | "
                  f"{s['query_accuracy']:.1%} | {s['mean_task_score']:.2f} | {cost} | {s['seconds_total']}s |")
    md += ["", "## Task x model (trials passed)", "", "| Task | " + " | ".join(f"`{m}`" for m in models) + " |",
           "|---|" + "---|" * len(models)]
    for tid, t in tasks.items():
        md.append(f"| {tid} {t['title']} | " + " | ".join(summary["matrix"][m].get(tid, "-") for m in models) + " |")
    md += ["", "## Failure attribution (wrong resources by author-assigned trap tag)", ""]
    for m in models:
        top = ", ".join(f"{k} {v}" for k, v in list(summary["traps"][m].items())[:8]) or "none"
        md.append(f"- `{m}`: {top}")
    md += ["", "## Wrong-rule fingerprint (failed queries reproduced exactly by a naive engine)", ""]
    for m in models:
        top = ", ".join(f"{k} {v}" for k, v in summary["fingerprints"][m].items()) or "none"
        md.append(f"- `{m}`: {top}")
    md += ["", "Errors / tool attempts per model: " + "; ".join(
        f"`{m}` {s['errors']} errors, {s['tool_attempt_trials']} trials with blocked tool attempts"
        for m, s in summary["models"].items())]
    (run_dir / "summary.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
