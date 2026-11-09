#!/usr/bin/env python3
"""Build the submission zip: python package.py [--out ../fhir-search-eval.zip]

1. Copies the repo to a staging dir (no .venv, caches, build artefacts).
2. Redacts organization policy-reminder lines that the CLI transport's managed
   settings made the Claude models append to some replies (they name the
   author's employer and an internal URL). A reminder line is replaced by
   "[organization policy reminder removed]". No reminder line contains any part
   of an answer (checked below), so grades cannot change.
3. Re-grades every staged trial and asserts the grades equal the originals.
4. Scans the staged tree for leftovers (employer name, home paths, key-like
   strings) and refuses to zip if any remain.
"""

import argparse
import json
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from fhireval.grader import grade  # noqa: E402
from fhireval.prompt import load_tasks  # noqa: E402

REMINDER = re.compile(r"athenahealth|go/claude-phi", re.I)
MARK = "[organization policy reminder removed]"
LEAK = re.compile(r"athena|go/claude|cabhishek|/Users/|sk-ant-|sk-proj-|Bearer [A-Za-z0-9]", re.I)
ANSWERISH = re.compile(r"[{}\[\]]|\bq\d+\b|(Observation|Patient|Condition|Encounter|Immunization|Medication\w*)/")
SKIP = {".venv", ".pytest_cache", "__pycache__", ".DS_Store", ".playwright-cli"}


def redact_text(text: str) -> tuple[str, int]:
    out, n = [], 0
    for line in text.split("\n"):
        if REMINDER.search(line):
            if ANSWERISH.search(line):
                raise SystemExit(f"refusing to redact a line with answer content: {line[:120]!r}")
            out.append(MARK)
            n += 1
        else:
            out.append(line)
    return "\n".join(out), n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT.parent / "fhir-search-eval.zip"))
    a = ap.parse_args()
    tasks = {t["id"]: t for t in load_tasks(ROOT / "tasks")}

    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp) / "fhir-search-eval"
        shutil.copytree(ROOT, stage, ignore=lambda d, names: [n for n in names if n in SKIP or n.endswith(".pyc")
                                                              or n.endswith(".zip")])
        redacted = 0
        for f in stage.rglob("trials.jsonl"):
            rows = [json.loads(l) for l in f.read_text().splitlines()]
            for r in rows:
                before = grade(tasks[r["task"]], r["text"]) if r["task"] in tasks else None
                r["text"], n = redact_text(r["text"])
                redacted += n
                if n and before is not None:
                    assert grade(tasks[r["task"]], r["text"]) == before, f"grade changed in {f}"
                if n:
                    r["redacted_policy_reminder_lines"] = n
            f.write_text("".join(json.dumps(r) + "\n" for r in rows))
        for f in list(stage.rglob("*.md")) + list(stage.rglob("*.log")):
            text, n = redact_text(f.read_text())
            if n:
                f.write_text(text)
                redacted += n

        leaks = [(p.relative_to(stage), m.group(0)) for p in stage.rglob("*") if p.is_file()
                 and p.suffix in (".md", ".json", ".jsonl", ".py", ".txt", ".log", ".toml", ".example", "")
                 for m in [LEAK.search(p.read_text(errors="ignore"))] if m]
        # package.py itself necessarily names the patterns it removes.
        leaks = [(p, s) for p, s in leaks if p.name != "package.py"]
        if leaks:
            for p, s in leaks[:20]:
                print(f"LEAK {p}: {s!r}")
            raise SystemExit("leak scan failed; nothing zipped")

        out = Path(a.out)
        out.unlink(missing_ok=True)
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            for p in sorted(stage.rglob("*")):
                if p.is_file():
                    z.write(p, p.relative_to(stage.parent))
        print(f"redacted {redacted} reminder lines; grades unchanged; leak scan clean")
        print(f"wrote {out} ({out.stat().st_size / 1e6:.1f} MB, {len(z.namelist())} files)")


if __name__ == "__main__":
    main()
