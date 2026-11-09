"""Reference FHIR R4 search engine for the subset of search used by this eval.

This is the reference solution: FHIR R4 search plus the server choices every
task prompt states (fhireval/prompt.py SERVER_CHOICES; the optional "rules"
prompt spells all of this out). Expected answers are produced by running this
engine over each task's resources and are cross-checked against the
hand-written answers in each task file (tests/test_grader.py).

Semantics:
  * Every date/dateTime is an interval [lo, hi) at its stated precision.
    Values with no offset are in the server's local time zone (IANA rules, DST).
  * Period = [lo(start), hi(end)); missing start -> -inf, missing end -> +inf.
  * Date prefixes, with S = search interval, T = target interval:
      eq: every instant of T is inside S     ne: not eq
      gt: some instant of T is at/after S's end      (t.hi > s.hi)
      ge: some instant of T is at/after S's start    (t.hi > s.lo)
      lt: some instant of T is before S's start      (t.lo < s.lo)
      le: some instant of T is before S's end        (t.lo < s.hi)
      sa: every instant of T is at/after S's end     (t.lo >= s.hi)
      eb: every instant of T is before S's start     (t.hi <= s.lo)
    The FHIR R4 prose leaves "range above/below" open to two readings; the
    profile pins this one (the common server behaviour) so tasks are unambiguous.
  * Quantity/number: eq/ne use the implicit range of the search number
    (+/- half a unit in its last digit); gt/lt/ge/le compare exactly.
  * Token: system|code, code, |code, system|; comma = OR; repeated param = AND.
    Identifier: system|value, value, :of-type=typeSystem|typeCode|value.
  * String: case/accent-insensitive starts-with (family names also by parts);
    :contains anywhere; :exact whole value, case/accent-sensitive.
  * Composite a$b: both halves satisfied by the same component (or resource).
  * Chains and _has: each evaluated independently (R4 3.1.1.4.15-16).
  * _include/_revinclude: added once, unfiltered; dangling references omitted.
"""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

NEG_INF = -math.inf
POS_INF = math.inf

_DATE_RE = re.compile(
    r"^(?P<y>\d{4})(?:-(?P<m>\d{2})(?:-(?P<d>\d{2})"
    r"(?:T(?P<H>\d{2}):(?P<M>\d{2})(?::(?P<S>\d{2}))?"
    r"(?P<tz>Z|[+-]\d{2}:\d{2})?)?)?)?$"
)


@dataclass(frozen=True)
class Interval:
    lo: float  # POSIX seconds, inclusive
    hi: float  # POSIX seconds, exclusive

    def __repr__(self) -> str:  # readable in test failures
        def f(x: float) -> str:
            if math.isinf(x):
                return "-inf" if x < 0 else "+inf"
            return datetime.fromtimestamp(x, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        return f"[{f(self.lo)}, {f(self.hi)})"


def _local_to_utc(naive: datetime, tz) -> float:
    return naive.replace(tzinfo=tz).timestamp()


def date_interval(value: str, server_tz: str) -> Interval:
    """Implicit range of a FHIR date/dateTime/instant string."""
    m = _DATE_RE.match(value)
    if not m:
        raise ValueError(f"unsupported date value: {value!r}")
    y = int(m["y"])
    if m["m"] is None:
        start, end = datetime(y, 1, 1), datetime(y + 1, 1, 1)
    elif m["d"] is None:
        mo = int(m["m"])
        start = datetime(y, mo, 1)
        end = datetime(y + (mo == 12), mo % 12 + 1, 1)
    elif m["H"] is None:
        start = datetime(y, int(m["m"]), int(m["d"]))
        end = start + timedelta(days=1)
    else:
        start = datetime(y, int(m["m"]), int(m["d"]), int(m["H"]), int(m["M"]), int(m["S"] or 0))
        end = start + (timedelta(seconds=1) if m["S"] is not None else timedelta(minutes=1))

    tz_s = m["tz"]
    if tz_s is None:
        tz = ZoneInfo(server_tz)
    elif tz_s == "Z":
        tz = timezone.utc
    else:
        sign = 1 if tz_s[0] == "+" else -1
        tz = timezone(sign * timedelta(hours=int(tz_s[1:3]), minutes=int(tz_s[4:6])))
    # Bounds are converted separately, so a local day that contains a DST
    # transition is 23 or 25 hours long.
    return Interval(_local_to_utc(start, tz), _local_to_utc(end, tz))


def period_interval(period: dict, server_tz: str) -> Interval:
    lo = date_interval(period["start"], server_tz).lo if "start" in period else NEG_INF
    hi = date_interval(period["end"], server_tz).hi if "end" in period else POS_INF
    return Interval(lo, hi)


DATE_PREFIXES = ("eq", "ne", "gt", "lt", "ge", "le", "sa", "eb")


def date_matches(prefix: str, s: Interval, t: Interval) -> bool:
    eq = s.lo <= t.lo and t.hi <= s.hi
    if prefix == "eq":
        return eq
    if prefix == "ne":
        return not eq
    if prefix == "gt":
        return t.hi > s.hi
    if prefix == "lt":
        return t.lo < s.lo
    if prefix == "ge":
        return t.hi > s.lo
    if prefix == "le":
        return t.lo < s.hi
    if prefix == "sa":
        return t.lo >= s.hi
    if prefix == "eb":
        return t.hi <= s.lo
    raise ValueError(prefix)


def number_range(text: str) -> tuple[Decimal, Decimal]:
    """[lo, hi) implied by the digits written, e.g. '100' -> [99.5, 100.5)."""
    if "e" in text.lower():
        raise ValueError("exponential notation is out of scope for this eval")
    v = Decimal(text)
    half = Decimal(5) * Decimal(10) ** (v.as_tuple().exponent - 1)
    return v - half, v + half


def number_matches(prefix: str, text: str, target: Decimal) -> bool:
    v = Decimal(text)
    if prefix in ("eq", "ne"):
        lo, hi = number_range(text)
        inside = lo <= target < hi
        return inside if prefix == "eq" else not inside
    return {
        "gt": target > v,
        "lt": target < v,
        "ge": target >= v,
        "le": target <= v,
    }[prefix]




# ---------------------------------------------------------------- indexing

def _codings(cc) -> list[dict]:
    if cc is None:
        return []
    if isinstance(cc, list):
        return [c for item in cc for c in _codings(item)]
    if "coding" in cc:
        return cc["coding"]
    if "code" in cc or "system" in cc:  # a bare Coding (e.g. Encounter.class)
        return [cc]
    return []


def _date_values(resource: dict, element: str, server_tz: str) -> list[Interval]:
    """Date-typed values of choice element `element` ([x]); strings, Age etc. are not indexed."""
    out = []
    for key, val in resource.items():
        if key == element + "DateTime" or key == element + "Instant":
            out.append(date_interval(val, server_tz))
        elif key == element + "Period" or (key == element and isinstance(val, dict)):
            out.append(period_interval(val, server_tz))
    return out


def _identifiers(resource: dict) -> list[dict]:
    """Identifiers as token values: code = Identifier.value, plus type codings for :of-type."""
    return [{"system": i["system"], "code": i.get("value"), "type": _codings(i.get("type"))}
            if "system" in i else {"code": i.get("value"), "type": _codings(i.get("type"))}
            for i in resource.get("identifier", [])]


_PART_SPLIT = re.compile(r"[\s\-]+")


def _family_parts(family: str) -> list[str]:
    parts = [p for p in _PART_SPLIT.split(family) if p]
    return parts if len(parts) > 1 else []


def _human_name_strings(resource: dict, which: str) -> tuple[list[str], list[str]]:
    """(whole values, extra family parts) for name / family / given."""
    whole, parts = [], []
    for n in resource.get("name", []):
        if which in ("name", "family") and "family" in n:
            whole.append(n["family"])
            parts += _family_parts(n["family"])
        if which in ("name", "given"):
            whole += n.get("given", [])
        if which == "name":
            whole += n.get("prefix", []) + n.get("suffix", [])
            if "text" in n:
                whole.append(n["text"])
    return whole, parts


def _search_params():
    def tok_cc(path):
        return lambda r, tz: _codings(r.get(path))

    def tok_code(path):
        return lambda r, tz: [{"code": r[path]}] if path in r else []

    def date_choice(el):
        return lambda r, tz: _date_values(r, el, tz)

    def qty(r, tz):
        return [r["valueQuantity"]] if "valueQuantity" in r else []

    def ref(path):
        def get(r, tz):
            v = r.get(path)
            items = v if isinstance(v, list) else ([v] if v else [])
            return [i["reference"] for i in items if "reference" in i]
        return get

    def names(which):
        return lambda r, tz: _human_name_strings(r, which)

    def components(r, tz):
        return [(_codings(c.get("code")), [c["valueQuantity"]] if "valueQuantity" in c else [])
                for c in r.get("component", [])]

    def code_value(r, tz):
        return [(_codings(r.get("code")), qty(r, tz))]

    return {
        ("Observation", "code"): ("token", tok_cc("code")),
        ("Observation", "status"): ("token", tok_code("status")),
        ("Observation", "date"): ("date", date_choice("effective")),
        ("Observation", "value-quantity"): ("quantity", qty),
        ("Observation", "patient"): ("reference", ref("subject")),
        ("Observation", "component-code"): ("token", lambda r, tz: [c for cc, _ in components(r, tz) for c in cc]),
        ("Observation", "component-value-quantity"): ("quantity", lambda r, tz: [q for _, qs in components(r, tz) for q in qs]),
        ("Observation", "component-code-value-quantity"): ("composite", components),
        ("Observation", "code-value-quantity"): ("composite", code_value),
        ("MedicationStatement", "effective"): ("date", date_choice("effective")),
        ("MedicationStatement", "status"): ("token", tok_code("status")),
        ("Immunization", "date"): ("date", date_choice("occurrence")),
        ("Immunization", "status"): ("token", tok_code("status")),
        ("Immunization", "vaccine-code"): ("token", tok_cc("vaccineCode")),
        ("Condition", "onset-date"): ("date", date_choice("onset")),
        ("Condition", "clinical-status"): ("token", tok_cc("clinicalStatus")),
        ("Encounter", "date"): ("date", lambda r, tz: [period_interval(r["period"], tz)] if "period" in r else []),
        ("Encounter", "class"): ("token", tok_cc("class")),
        ("Encounter", "status"): ("token", tok_code("status")),
        ("Patient", "name"): ("string", names("name")),
        ("Patient", "family"): ("string", names("family")),
        ("Patient", "given"): ("string", names("given")),
        ("Patient", "identifier"): ("token", lambda r, tz: _identifiers(r)),
        ("Patient", "gender"): ("token", tok_code("gender")),
        ("Patient", "birthdate"): ("date", lambda r, tz: [date_interval(r["birthDate"], tz)] if "birthDate" in r else []),
        ("Provenance", "target"): ("reference", ref("target")),
    }


SEARCH_PARAMS = _search_params()


# ---------------------------------------------------------------- matching

def _token_value_matches(value: str, coding: dict) -> bool:
    if "|" in value:
        system, code = value.split("|", 1)
        if system == "":
            return "system" not in coding and coding.get("code") == code
        if code == "":
            return coding.get("system") == system
        return coding.get("system") == system and coding.get("code") == code
    return coding.get("code") == value


def _of_type_matches(value: str, ident: dict) -> bool:
    system, code, val = value.split("|", 2)
    return ident.get("code") == val and any(
        t.get("system") == system and t.get("code") == code for t in ident["type"])


def _split_prefix(value: str, allowed) -> tuple[str, str]:
    if len(value) > 2 and value[:2] in allowed and not value[:2].isdigit():
        return value[:2], value[2:]
    return "eq", value


def _quantity_matches(value: str, q: dict) -> bool:
    parts = value.split("|")
    num = parts[0]
    system = parts[1] if len(parts) > 1 else ""
    code = parts[2] if len(parts) > 2 else ""
    if code:
        if system:
            if q.get("system") != system or q.get("code") != code:
                return False
        elif q.get("code") != code and q.get("unit") != code:
            return False
    if "value" not in q:
        return False
    prefix, number = _split_prefix(num, ("eq", "ne", "gt", "lt", "ge", "le"))
    return number_matches(prefix, number, Decimal(str(q["value"])))


def _norm(s: str) -> str:
    """Case- and accent-insensitive form used by default string search."""
    decomposed = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).casefold()


def _string_matches(modifier: str, value: str, whole: list[str], parts: list[str]) -> bool:
    if modifier == "exact":
        return value in whole
    v = _norm(value)
    if modifier == "contains":
        return any(v in _norm(s) for s in whole)
    return any(_norm(s).startswith(v) for s in whole + parts)


def _ref_matches(value: str, ref: str) -> bool:
    return ref == value or ref.split("/")[-1] == value


class _Ctx:
    def __init__(self, resources: list[dict], server_tz: str):
        self.resources = resources
        self.tz = server_tz
        self.by_ref = {f"{r['resourceType']}/{r['id']}": r for r in resources}


def _param_matches(resource: dict, name: str, value: str, ctx: _Ctx) -> bool:
    if name.startswith("_has:"):
        # _has:<Type>:<reference param>:<param on Type>  -- each _has evaluated independently
        _, src_type, ref_param, rest = name.split(":", 3)
        me = f"{resource['resourceType']}/{resource['id']}"
        _, extract = SEARCH_PARAMS[(src_type, ref_param)]
        return any(
            s["resourceType"] == src_type
            and me in extract(s, ctx.tz)
            and _param_matches(s, rest, value, ctx)
            for s in ctx.resources)

    if "." in name:
        # chained: <reference param>[:<Type>].<param on target>  -- each chain independent
        head, tail = name.split(".", 1)
        ref_param, _, target_type = head.partition(":")
        _, extract = SEARCH_PARAMS[(resource["resourceType"], ref_param)]
        for ref in extract(resource, ctx.tz):
            target = ctx.by_ref.get(ref)
            if target and (not target_type or target["resourceType"] == target_type):
                if _param_matches(target, tail, value, ctx):
                    return True
        return False

    base, _, modifier = name.partition(":")
    ptype, extract = SEARCH_PARAMS[(resource["resourceType"], base)]
    values = extract(resource, ctx.tz)
    if ptype == "string":
        whole, parts = values
        has_value = bool(whole)
    else:
        has_value = bool(values)

    if modifier == "missing":
        return (not has_value) == (value == "true")

    alternatives = value.split(",")  # OR
    if ptype == "token":
        if modifier == "of-type":
            return any(_of_type_matches(v, i) for v in alternatives for i in values)
        hit = any(_token_value_matches(v, c) for v in alternatives for c in values)
        if modifier == "not":
            return not hit
        if modifier:
            raise ValueError(f"unsupported modifier {modifier}")
        return hit
    if ptype == "string":
        if modifier not in ("", "exact", "contains"):
            raise ValueError(f"unsupported modifier {modifier}")
        return any(_string_matches(modifier, v, whole, parts) for v in alternatives)
    if modifier:
        raise ValueError(f"unsupported modifier {modifier}")
    if ptype == "date":
        for alt in alternatives:
            prefix, raw = _split_prefix(alt, DATE_PREFIXES)
            s = date_interval(raw, ctx.tz)
            if any(date_matches(prefix, s, t) for t in values):
                return True
        return False
    if ptype == "quantity":
        return any(_quantity_matches(alt, q) for alt in alternatives for q in values)
    if ptype == "reference":
        return any(_ref_matches(alt, r) for alt in alternatives for r in values)
    if ptype == "composite":
        # Both parts must be satisfied by the SAME group (component / resource).
        for alt in alternatives:
            tok, qv = alt.split("$", 1)
            if any(any(_token_value_matches(tok, c) for c in codes) and
                   any(_quantity_matches(qv, q) for q in qtys) for codes, qtys in values):
                return True
        return False
    raise ValueError(ptype)


def parse_query(query: str) -> tuple[str, list[tuple[str, str]]]:
    """'Observation?code=x&date=ge2024' -> ('Observation', [('code','x'), ('date','ge2024')])."""
    rtype, _, qs = query.partition("?")
    params = []
    for part in qs.split("&"):
        if part:
            k, _, v = part.partition("=")
            params.append((k, v))
    return rtype, params


def run_query(query: str, resources: list[dict], server_tz: str):
    """Sorted list of matching references, or {"match": [...], "include": [...]}
    when the query uses _include / _revinclude."""
    rtype, params = parse_query(query)
    ctx = _Ctx(resources, server_tz)
    filters = [(k, v) for k, v in params if k not in ("_include", "_revinclude")]
    matches = [r for r in resources if r["resourceType"] == rtype
               and all(_param_matches(r, k, v, ctx) for k, v in filters)]
    match_refs = {f"{r['resourceType']}/{r['id']}" for r in matches}
    if len(filters) == len(params):
        return sorted(match_refs)

    included = set()
    for k, v in params:
        if k not in ("_include", "_revinclude"):
            continue
        src_type, ref_param = v.split(":")[:2]
        _, extract = SEARCH_PARAMS[(src_type, ref_param)]
        if k == "_include":
            for r in matches:
                included |= {ref for ref in extract(r, server_tz) if ref in ctx.by_ref}
        elif k == "_revinclude":
            for s in resources:
                if s["resourceType"] == src_type and set(extract(s, server_tz)) & match_refs:
                    included.add(f"{s['resourceType']}/{s['id']}")
    return {"match": sorted(match_refs), "include": sorted(included - match_refs)}


def solve_task(task: dict) -> dict:
    tz = task["server_timezone"]
    return {q["id"]: run_query(q["query"], task["resources"], tz) for q in task["queries"]}
