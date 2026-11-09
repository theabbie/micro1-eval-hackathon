"""Reference solution: run the reference engine over every task and write
reference/expected_answers.json. Usage: python reference/solve.py"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fhireval.engine import solve_task  # noqa: E402
from fhireval.prompt import load_tasks  # noqa: E402


def main() -> None:
    out = {t["id"]: solve_task(t) for t in load_tasks(ROOT / "tasks")}
    path = ROOT / "reference" / "expected_answers.json"
    path.write_text(json.dumps(out, indent=2) + "\n")
    print(f"wrote {path.relative_to(ROOT)} ({sum(len(v) for v in out.values())} queries)")


if __name__ == "__main__":
    main()
