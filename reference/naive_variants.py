"""Plausible-but-wrong search engines.

Each variant changes ONE rule of the reference engine to a mistake an
implementer (or a model) plausibly makes. They serve two purposes:
  1. Grader validation: every variant must FAIL at least one task
     (tests/test_grader.py), proving the grader rejects realistic wrong answers.
  2. Failure analysis: analyze.py measures how often a model's wrong answers
     agree with each variant, i.e. which wrong rule the model seems to apply.
"""

from __future__ import annotations

import sys
from contextlib import contextmanager
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fhireval import engine  # noqa: E402

_real_date_interval = engine.date_interval
_real_date_matches = engine.date_matches
_real_number_matches = engine.number_matches

# Standard-time offsets for the zones used in the tasks (no DST).
_STD = {"America/New_York": "Etc/GMT+5", "America/Chicago": "Etc/GMT+6",
        "America/Los_Angeles": "Etc/GMT+8"}


def _utc_local(value, server_tz):
    return _real_date_interval(value, "UTC")


def _fixed_offset(value, server_tz):
    return _real_date_interval(value, _STD.get(server_tz, server_tz))


def _point_target(value, server_tz):
    iv = _real_date_interval(value, server_tz)
    return engine.Interval(iv.lo, iv.lo + 1)


def _overlap_eq(prefix, s, t):
    if prefix in ("eq", "ne"):
        ov = t.lo < s.hi and s.lo < t.hi
        return ov if prefix == "eq" else not ov
    return _real_date_matches(prefix, s, t)


def _literal_range_above(prefix, s, t):
    # "range above the value = the value and up": gt behaves like ge, lt like le.
    if prefix == "gt":
        return t.hi > s.lo
    if prefix == "lt":
        return t.lo < s.hi
    return _real_date_matches(prefix, s, t)


def _exact_number_eq(prefix, text, target):
    if prefix == "eq":
        return target == Decimal(text)
    if prefix == "ne":
        return target != Decimal(text)
    return _real_number_matches(prefix, text, target)


@contextmanager
def _point_targets_only():
    """Resource values are points at their start; periods collapse to their start."""
    real_period = engine.period_interval

    def period(p, tz):
        iv = real_period(p, tz)
        return engine.Interval(iv.lo, iv.lo + 1) if iv.lo != engine.NEG_INF else iv

    real_values = engine._date_values

    def values(resource, element, tz):
        with mock.patch.object(engine, "date_interval", _point_target), \
             mock.patch.object(engine, "period_interval", period):
            return real_values(resource, element, tz)

    with mock.patch.object(engine, "_date_values", values):
        # Encounter.date calls period_interval directly via its lambda.
        with mock.patch.object(engine, "period_interval", period):
            # Search values must keep their real intervals.
            yield


VARIANTS = {
    "offsetless-as-UTC": lambda: mock.patch.object(engine, "date_interval", _utc_local),
    "fixed-std-offset-no-DST": lambda: mock.patch.object(engine, "date_interval", _fixed_offset),
    "eq-means-overlap": lambda: mock.patch.object(engine, "date_matches", _overlap_eq),
    "gt-lt-from-value-not-range-end": lambda: mock.patch.object(engine, "date_matches", _literal_range_above),
    "targets-as-points": _point_targets_only,
    "quantity-eq-exact": lambda: mock.patch.object(engine, "number_matches", _exact_number_eq),
    "string-case-and-accent-sensitive": lambda: mock.patch.object(engine, "_norm", lambda s: s),
    "string-no-family-parts": lambda: mock.patch.object(engine, "_family_parts", lambda f: []),
}


def solve_with(variant: str, task: dict) -> dict[str, list[str]]:
    with VARIANTS[variant]():
        return engine.solve_task(task)
