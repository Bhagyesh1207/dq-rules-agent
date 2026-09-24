"""Turn a profile into data quality rules.

Every rule carries a rationale that points back to the profiling evidence, so a
reviewer can see why it was suggested and accept or reject it.
"""
from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any

from .profiler import PATTERNS

ID_HINT = re.compile(r"(^id$|_id$|^id_|uuid|key$|number$|code$)", re.I)


@dataclass
class Rule:
    rule_id: str
    column: str | None
    check: str
    params: dict[str, Any] = field(default_factory=dict)
    severity: str = "error"          # error | warning
    confidence: float = 1.0          # share of current rows that already pass
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _nice_floor(x: float) -> float:
    if x == 0:
        return 0.0
    mag = 10 ** math.floor(math.log10(abs(x)))
    return math.floor(x / mag) * mag


def _nice_ceil(x: float) -> float:
    if x == 0:
        return 0.0
    mag = 10 ** math.floor(math.log10(abs(x)))
    return math.ceil(x / mag) * mag


def _column_rules(c: dict[str, Any], n_rows: int) -> list[Rule]:
    col, kind = c["name"], c["kind"]
    rules: list[Rule] = []
    add = rules.append
    rid = lambda check: f"{col}.{check}"

    # completeness
    if c["null_count"] == 0 and n_rows > 0:
        add(Rule(rid("not_null"), col, "not_null", {}, "error", 1.0,
                 f"0 of {n_rows} rows are null."))
    elif c["null_rate"] <= 0.2:
        limit = max(0.01, math.ceil(c["null_rate"] * 1.5 * 100) / 100)
        add(Rule(rid("max_null_rate"), col, "max_null_rate", {"max_rate": limit}, "warning",
                 1.0, f"{c['null_rate']:.1%} null today; alert if it rises above {limit:.0%}."))

    # type
    if kind in ("integer", "float", "datetime", "boolean"):
        add(Rule(rid("type"), col, "type", {"kind": kind}, "error", 1.0,
                 f"Profiler inferred '{kind}' for all non-null values."))

    # uniqueness
    looks_like_id = bool(ID_HINT.search(col))
    pats = c.get("patterns") or {}
    keyish_pattern = max(pats.get("email", 0), pats.get("uuid", 0)) >= 0.9
    if c["distinct"] and c["unique_rate"] == 1.0 and (looks_like_id or keyish_pattern) and kind != "datetime":
        add(Rule(rid("unique"), col, "unique", {}, "error", 1.0,
                 f"All {c['distinct']} non-null values are distinct"
                 + (" and the name looks like a key." if looks_like_id else ".")))
    elif looks_like_id and c["unique_rate"] >= 0.97 and c["distinct"] > 10:
        add(Rule(rid("unique"), col, "unique", {}, "error", c["unique_rate"],
                 f"Key-like column is {c['unique_rate']:.1%} unique; the duplicates are likely errors."))

    # numeric ranges
    if kind in ("integer", "float") and "min" in c:
        lo, hi = c["min"], c["max"]
        if c["negative_count"] == 0 and not looks_like_id:
            add(Rule(rid("non_negative"), col, "between", {"min": 0}, "error", 1.0,
                     f"No negative values across {n_rows - c['null_count']} rows (min {lo:g})."))
        span = hi - lo
        if span > 0 and not looks_like_id:
            p_lo = lo - 0.1 * span
            p_hi = hi + 0.1 * span
            b_lo = max(0.0, _nice_floor(p_lo)) if lo >= 0 else _nice_floor(p_lo)
            b_hi = _nice_ceil(p_hi)
            inside = 1.0
            add(Rule(rid("expected_range"), col, "between", {"min": b_lo, "max": b_hi}, "warning",
                     inside,
                     f"Observed {lo:g} to {hi:g} (median {c['median']:g}, {c['outlier_count']} IQR outliers). "
                     f"Values outside {b_lo:g} to {b_hi:g} need review."))

    # dates
    if kind == "datetime" and "max" in c:
        today = date.today().isoformat()
        if c["max"] <= today:
            add(Rule(rid("not_in_future"), col, "date_not_after", {"max": "today"}, "error", 1.0,
                     f"Latest value is {c['max']}; no future dates seen."))
        add(Rule(rid("date_floor"), col, "date_not_before", {"min": c["min"]}, "warning", 1.0,
                 f"Earliest value is {c['min']}."))

    # categorical
    non_null = n_rows - c["null_count"]
    if kind == "string" and 1 < c["distinct"] <= 15 and non_null >= 20 \
            and c["distinct"] / max(1, non_null) <= 0.2 and not looks_like_id and "top_values" in c:
        vals = sorted(c["top_values"].keys())
        add(Rule(rid("allowed_values"), col, "in_set", {"values": vals}, "error", 1.0,
                 f"Only {c['distinct']} distinct values in {non_null} rows; treat as a closed list."))
    elif kind == "integer" and 1 < c["distinct"] <= 15 and non_null >= 20 and not looks_like_id \
            and c["distinct"] / max(1, non_null) <= 0.2:
        pass

    # patterns
    if pats and kind == "string":
        best, rate = max(pats.items(), key=lambda kv: kv[1])
        if rate >= 0.9:
            add(Rule(rid(f"pattern_{best}"), col, "regex", {"pattern": PATTERNS[best], "name": best},
                     "error" if rate >= 0.99 else "warning", rate,
                     f"{rate:.1%} of values match the {best} pattern"
                     + ("." if rate == 1 else "; the rest are likely bad entries.")))

    # length
    if kind == "string" and "min_length" in c and c["max_length"] <= 64 and not pats.get("email"):
        if c["min_length"] == c["max_length"]:
            add(Rule(rid("fixed_length"), col, "length", {"min": c["min_length"], "max": c["max_length"]},
                     "warning", 1.0, f"Every value is exactly {c['min_length']} characters."))
        elif c["max_length"] > 0:
            add(Rule(rid("length"), col, "length", {"min": max(1, c["min_length"]), "max": c["max_length"]},
                     "warning", 1.0, f"Lengths range from {c['min_length']} to {c['max_length']}."))

    # whitespace hygiene
    if c.get("has_leading_trailing_space"):
        share = c["has_leading_trailing_space"] / max(1, non_null)
        add(Rule(rid("trimmed"), col, "no_surrounding_whitespace", {}, "warning", round(1 - share, 4),
                 f"{c['has_leading_trailing_space']} values have leading or trailing spaces."))
    return rules


def suggest_rules(profile: dict[str, Any]) -> list[Rule]:
    n = profile["row_count"]
    rules: list[Rule] = [
        Rule("table.row_count", None, "row_count_between",
             {"min": max(1, int(n * 0.5)), "max": int(n * 2) if n else None}, "warning", 1.0,
             f"Current load has {n} rows; flag loads under half or over double that."),
    ]
    rules.append(Rule("table.no_duplicate_rows", None, "no_duplicate_rows", {},
                      "error" if profile["duplicate_rows"] == 0 else "warning",
                      round(1 - profile["duplicate_rows"] / max(1, n), 4),
                      f"{profile['duplicate_rows']} fully duplicated rows found."))
    for c in profile["columns"]:
        rules.extend(_column_rules(c, n))
    return rules
