#!/usr/bin/env bash
# One command from a clean checkout:   bash reproduce.sh
#   1. creates .venv and installs requirements.txt
#   2. runs the grader/reference validation suite (79 tests, no API calls)
#   3. grades the reference solution (oracle) through the same grader
#   4. regenerates the headline table from the recorded raw replies
#   5. only if RUN_MODELS=1: re-runs the models through the APIs
#      (needs ANTHROPIC_API_KEY and/or OPENAI_API_KEY; ~15 min with all five models)
set -euo pipefail
cd "$(dirname "$0")"
python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt
.venv/bin/python -m pytest -q
.venv/bin/python run_eval.py --oracle
.venv/bin/python analyze.py --run main-v2-20261030 | sed -n '1,9p'

if [ "${RUN_MODELS:-0}" = "1" ]; then
  RUN="repro-$(date -u +%Y%m%dT%H%M%SZ)"
  if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
    .venv/bin/python run_eval.py --backend anthropic-api --models claude-opus-5-5 claude-sonnet-5-5 claude-haiku-5-5 \
      --trials 3 --effort medium --run "$RUN"
  fi
  if [ -n "${OPENAI_API_KEY:-}" ]; then
    .venv/bin/python run_eval.py --backend openai-api --models gpt-6.1-sol gpt-5.6-luna \
      --trials 3 --effort medium --run "$RUN"
  fi
  .venv/bin/python analyze.py --run "$RUN"
fi
