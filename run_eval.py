#!/usr/bin/env python3
"""Run the eval: every task x model x trial, fresh single-turn context each time.

Examples
  python run_eval.py --backend anthropic-api --models claude-opus-5-5 claude-haiku-5-5 --trials 3 --effort medium
  python run_eval.py --backend openai-api --models gpt-6.1-sol --trials 3
  python run_eval.py --oracle            # reference solution through the same grader (no API calls)

Output: results/runs/<run>/trials.jsonl (one record per trial, raw reply included)
        transcripts/<run>/<model>/<task>_t<k>.md (prompt + reply + grade)
Re-running with the same --run resumes: finished trials are skipped.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from fhireval.backends import BACKENDS, available  # noqa: E402
from fhireval.engine import solve_task  # noqa: E402
from fhireval.grader import answer_text, grade  # noqa: E402
from fhireval.prompt import build_prompt, load_tasks  # noqa: E402

_lock = threading.Lock()


def _transcript(path: Path, task, model, k, prompt, rec):
    g = rec["grade"]
    lines = [f"# {task['id']} {task['title']} | {model} | trial {k}", "",
             f"- passed: **{g['passed']}**  score: {g['score']:.2f}  parsed: {g['parsed']}",
             f"- resolved model: `{rec['resolved_model']}`  tool attempts: {rec['tool_attempts']}", ""]
    for qid, v in g["queries"].items():
        mark = "OK " if v["correct"] else "XX "
        extra = "" if v["correct"] else f"  false+ {v['false_positives']}  false- {v['false_negatives']}"
        lines.append(f"    {mark}{qid}{extra}")
    lines += ["", "## Prompt", "", "```text", prompt, "```", "", "## Reply", "", rec["text"] or "(empty)", ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=sorted(BACKENDS))
    ap.add_argument("--models", nargs="+", default=[])
    ap.add_argument("--trials", type=int, default=3)
    ap.add_argument("--tasks", nargs="*", help="task ids, default all")
    ap.add_argument("--effort", default=None, help="reasoning effort passed to the backend")
    ap.add_argument("--run", default=None, help="run name (default: timestamp)")
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--profile", choices=["spec", "rules"], default="spec",
                    help="spec: FHIR spec + clarifications only (headline); rules: full rule sheet (ablation)")
    ap.add_argument("--oracle", action="store_true", help="grade the reference solution instead of a model")
    args = ap.parse_args()

    tasks = [t for t in load_tasks(ROOT / "tasks") if not args.tasks or t["id"] in args.tasks]
    run = args.run or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if args.oracle:
        for t in tasks:
            g = grade(t, answer_text(solve_task(t)))
            print(f"oracle {t['id']}: passed={g['passed']} score={g['score']:.2f}")
        return

    out_dir = ROOT / "results" / "runs" / run
    out_dir.mkdir(parents=True, exist_ok=True)
    trials_path = out_dir / "trials.jsonl"

    if not args.backend or not args.models:
        ap.error("--backend and --models are required (or use --oracle)")
    if not available(args.backend):
        ap.error(f"backend {args.backend} unavailable (missing API key or CLI)")

    done = set()
    if trials_path.exists():
        for line in trials_path.read_text().splitlines():
            r = json.loads(line)
            done.add((r["model"], r["task"], r["trial"]))

    meta = {"run": run, "backend": args.backend, "models": args.models, "trials": args.trials,
            "effort": args.effort, "profile": args.profile, "started_utc": datetime.now(timezone.utc).isoformat()}
    (out_dir / f"meta_{args.backend}.json").write_text(json.dumps(meta, indent=2))

    jobs = [(m, t, k) for m in args.models for t in tasks for k in range(1, args.trials + 1)
            if (m, t["id"], k) not in done]
    print(f"run {run}: {len(jobs)} trials to do ({len(done)} already done)")
    backend = BACKENDS[args.backend]

    def one(model, task, k):
        prompt = build_prompt(task, args.profile)
        t0 = time.time()
        err, res = None, None
        for attempt in range(3):
            try:
                res = backend(prompt, model, effort=args.effort)
                err = None
                break
            except Exception as e:  # transport failure: retry, then record as an error trial
                err = f"{type(e).__name__}: {e}"
                time.sleep(10 * (attempt + 1))
        text = res["text"] if res else ""
        rec = {"run": run, "backend": args.backend, "model": model, "task": task["id"], "trial": k,
               "effort": args.effort, "profile": args.profile, "utc": datetime.now(timezone.utc).isoformat(),
               "seconds": round(time.time() - t0, 1), "error": err, "text": text,
               "resolved_model": res["model"] if res else None,
               "usage": res["usage"] if res else None, "cost_usd": res["cost_usd"] if res else None,
               "tool_attempts": res["tool_attempts"] if res else 0,
               "transport": res["raw"] if res else None,
               "grade": grade(task, text)}
        with _lock:
            with trials_path.open("a") as f:
                f.write(json.dumps(rec) + "\n")
        _transcript(ROOT / "transcripts" / run / model / f"{task['id']}_t{k}.md", task, model, k, prompt, rec)
        return rec

    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futs = [pool.submit(one, *j) for j in jobs]
        for f in as_completed(futs):
            r = f.result()
            status = "ERROR " + r["error"][:80] if r["error"] else f"score={r['grade']['score']:.2f} pass={r['grade']['passed']}"
            print(f"{r['model']:<20} {r['task']} t{r['trial']} {r['seconds']:>6}s {status}", flush=True)


if __name__ == "__main__":
    main()
