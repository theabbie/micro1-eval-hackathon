"""Builds the single-turn prompt for a task. Only these fields reach the model:
scenario, server_timezone, resources, query strings. Expected answers,
rationales, traps and why_hard stay hidden."""

from __future__ import annotations

import json

PARAMS = """\
Search parameters defined on this server (name, type, path)
  Observation:  code (token, Observation.code), status (token), date (date, Observation.effective[x]),
                value-quantity (quantity, Observation.valueQuantity), patient (reference, Observation.subject),
                component-code (token, Observation.component.code),
                component-value-quantity (quantity, Observation.component.valueQuantity),
                component-code-value-quantity (composite: component-code $ component-value-quantity),
                code-value-quantity (composite: code $ value-quantity)
  MedicationStatement: effective (date, MedicationStatement.effective[x]), status (token)
  Immunization: date (date, Immunization.occurrence[x]), status (token), vaccine-code (token)
  Condition:    onset-date (date, Condition.onsetDateTime | Condition.onsetPeriod), clinical-status (token)
  Encounter:    date (date, Encounter.period), class (token, Encounter.class), status (token)
  Patient:      name (string, HumanName), family (string, HumanName.family), given (string, HumanName.given),
                identifier (token, Patient.identifier), gender (token), birthdate (date, Patient.birthDate)
  Provenance:   target (reference, Provenance.target)
"""

SERVER_CHOICES = """\
Where the specification leaves a choice to the server, this server does the following:
  * Date/dateTime values with no offset (including date-only, year-month and year values),
    in resources and in queries, are in the server's local time zone (given per task, an
    IANA zone with real DST rules).
  * For date prefixes, the "range above" a search value starts at the END of the search
    value's implicit range, and the "range below" ends at its START. ge additionally matches
    any target that overlaps the search range; le likewise.
  * :not returns resources with no value for the parameter as well.
  * Only date-typed values (date, dateTime, instant, Period) are indexed by date parameters.
  * No unit conversion, no terminology subsumption; code matching is case-sensitive.
  * Numbers and quantities: only the SEARCH value has an implicit range (from the digits
    written), used by eq and ne. Values stored in resources are exact points; their own
    written precision is ignored. Prefixes gt, lt, ge, le compare exactly, ignoring the
    search value's implicit precision too (as the R4 number section states). (The R4 prefix
    table also describes a range reading for decimals; this server does not use it.)
  * name searches family, given, prefix, suffix and text of every HumanName on the Patient.
    For default (no modifier) string matching, family names are also matched by their parts
    (split on spaces and hyphens), for both name and family. :exact and :contains compare
    against whole element values only. No other punctuation handling.
"""

PROFILE = PARAMS + "\n" + SERVER_CHOICES + """
Detailed rules (this server)
  General
  * Parameters joined by & must all match (AND). Repeating a parameter name is also AND,
    each occurrence evaluated independently. Comma-separated values are OR.
  * A resource with no value for a parameter never matches that parameter, whatever the
    prefix (including ne). Exceptions: :missing and :not.
  * name:missing=true matches resources with no value for the parameter; =false those with one.
  * If an element repeats (several codings, components, names), a parameter matches if ANY
    value matches. Separate parameters may be satisfied by different repeats.
  Dates
  * Every date, dateTime or instant (in a resource or in a query) denotes a half-open
    interval [start, end) set by its precision: year, month, day, minute or second.
  * Period: from the start of Period.start's interval to the end of Period.end's interval;
    a missing start is unbounded in the past, a missing end unbounded in the future.
  * S = search interval, T = resource interval. No prefix means eq.
      eq every instant of T is inside S        ne not eq
      gt some instant of T at/after S's end    ge some instant of T at/after S's start
      lt some instant of T before S's start    le some instant of T before S's end
      sa every instant of T at/after S's end   eb every instant of T before S's start
  Tokens
  * system|code exact; code alone any system; |code no system; system| any code.
  * Identifier: system|value or value; :of-type=typeSystem|typeCode|value.
  * :not matches resources with no matching value, including those with no value.
  Quantities: [prefix][number]|[system]|[code]
  * system+code must both equal; ||code matches Quantity.code or Quantity.unit; number only = any units.
  * eq/ne use the implicit range of the number as written ("100" = [99.5, 100.5),
    "100.0" = [99.95, 100.05)); gt/lt/ge/le compare exactly.
  Strings
  * Default: case- and accent-insensitive, value starts with the search text.
    :contains anywhere (case/accent-insensitive); :exact whole value, case/accent-sensitive.
  Composite, chains, _has, includes
  * Composite a$b: both parts must match the SAME component (or the resource itself for
    code-value-quantity).
  * ref.param (chain): some referenced resource on this server matches param.
  * _has:Type:refParam:param=v: some Type resource referencing this one via refParam matches.
    Every chain and every _has is evaluated independently.
  * _include=Type:refParam adds resources referenced by the matches (if on this server);
    _revinclude=Type:refParam adds resources that reference a match. Each resource once;
    included resources are not filtered by the search criteria.
"""

SPEC_PROFILE = """\
SERVER BEHAVIOUR
The server implements FHIR R4 search exactly as specified at http://hl7.org/fhir/R4/search.html
(prefixes, implicit ranges, token, string and composite syntax, modifiers, chaining, _has,
_include/_revinclude, AND/OR rules).

""" + PARAMS + "\n" + SERVER_CHOICES

INSTRUCTIONS = """\
For each query, determine exactly which of the resources above the server returns.

Reason as carefully as you need. Then end your reply with ONE fenced ```json block
containing a single object that maps every query id to the sorted list of matching
resource references written as "ResourceType/id". Use [] when nothing matches.
Example shape: {"q1": ["Observation/x-01", "Observation/x-02"], "q2": []}
For a query that uses _include or _revinclude, give an object instead, separating the
resources that match the search criteria from those added by the include(s):
  {"q5": {"match": ["Observation/x-01"], "include": ["Patient/p-1"]}}
"""


PROFILES = {"spec": SPEC_PROFILE, "rules": PROFILE}


def build_prompt(task: dict, profile: str = "spec") -> str:
    resources = "\n".join(json.dumps(r, separators=(",", ":")) for r in task["resources"])
    queries = "\n".join(f"{q['id']}: GET [base]/{q['query']}" for q in task["queries"])
    return (
        f"You are reviewing FHIR R4 search behaviour for a healthcare integration.\n\n"
        f"{PROFILES[profile]}\n"
        f"TASK {task['id']}: {task['title']}\n"
        f"Scenario: {task['scenario']}\n"
        f"Server local time zone: {task['server_timezone']}\n\n"
        f"RESOURCES (one JSON resource per line; these are the only resources on the server)\n"
        f"{resources}\n\n"
        f"QUERIES\n{queries}\n\n"
        f"{INSTRUCTIONS}"
    )


def load_tasks(task_dir) -> list[dict]:
    from pathlib import Path

    return [json.loads(p.read_text()) for p in sorted(Path(task_dir).glob("T*.json"))]
