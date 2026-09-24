"""Run generated rules against a DataFrame and report failures."""
from __future__ import annotations

import re
import warnings
from datetime import date
from typing import Any, Iterable

import pandas as pd

from .rules import Rule


def _as_rule(r: Rule | dict) -> Rule:
    return r if isinstance(r, Rule) else Rule(**r)


def _failing_mask(df: pd.DataFrame, r: Rule) -> pd.Series | None:
    if r.column is not None and r.column not in df.columns:
        return None
    s = df[r.column] if r.column else None
    p = r.params
    if r.check == "not_null":
        return s.isna() | (s.astype(str).str.strip() == "")
    nn = s.notna() if s is not None else None
    if r.check == "unique":
        return nn & s.duplicated(keep=False)
    if r.check == "between":
        num = pd.to_numeric(s, errors="coerce")
        bad = pd.Series(False, index=df.index)
        if p.get("min") is not None:
            bad |= num < p["min"]
        if p.get("max") is not None:
            bad |= num > p["max"]
        return nn & bad
    if r.check == "type":
        if p["kind"] in ("integer", "float"):
            num = pd.to_numeric(s, errors="coerce")
            bad = num.isna()
            if p["kind"] == "integer":
                bad |= (num % 1 != 0) & num.notna()
            return nn & bad
        if p["kind"] == "datetime":
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                return nn & pd.to_datetime(s.astype(str), errors="coerce", format="mixed").isna()
        if p["kind"] == "boolean":
            ok = s.astype(str).str.lower().str.strip().isin(["true", "false", "yes", "no", "0", "1", "y", "n"])
            return nn & ~ok
    if r.check == "in_set":
        return nn & ~s.astype(str).isin([str(v) for v in p["values"]])
    if r.check == "regex":
        return nn & ~s.astype(str).str.strip().str.match(re.compile(p["pattern"]))
    if r.check == "length":
        ln = s.astype(str).str.strip().str.len()
        return nn & ((ln < p["min"]) | (ln > p["max"]))
    if r.check == "no_surrounding_whitespace":
        return nn & (s.astype(str) != s.astype(str).str.strip())
    if r.check in ("date_not_after", "date_not_before"):
        dt = pd.to_datetime(s.astype(str), errors="coerce", format="mixed")
        if r.check == "date_not_after":
            lim = pd.Timestamp(date.today()) if p["max"] == "today" else pd.Timestamp(p["max"])
            return nn & (dt > lim)
        return nn & (dt < pd.Timestamp(p["min"]))
    if r.check == "no_duplicate_rows":
        return df.duplicated(keep=False)
    return None


def validate(df: pd.DataFrame, rules: Iterable[Rule | dict]) -> list[dict[str, Any]]:
    results = []
    for raw in rules:
        r = _as_rule(raw)
        if r.check == "row_count_between":
            n = len(df)
            ok = (r.params.get("min") is None or n >= r.params["min"]) and \
                 (r.params.get("max") is None or n <= r.params["max"])
            results.append({"rule_id": r.rule_id, "severity": r.severity, "passed": ok,
                            "failed_rows": 0 if ok else n, "examples": [] if ok else [n]})
            continue
        if r.check == "max_null_rate":
            s = df[r.column]
            rate = float((s.isna() | (s.astype(str).str.strip() == "")).mean())
            ok = rate <= r.params["max_rate"]
            results.append({"rule_id": r.rule_id, "severity": r.severity, "passed": ok,
                            "failed_rows": 0 if ok else int(rate * len(df)),
                            "examples": [] if ok else [f"null rate {rate:.1%}"]})
            continue
        mask = _failing_mask(df, r)
        if mask is None:
            results.append({"rule_id": r.rule_id, "severity": r.severity, "passed": False,
                            "failed_rows": None, "examples": ["column missing or check unsupported"]})
            continue
        mask = mask.fillna(False).astype(bool)
        bad = int(mask.sum())
        ex = df.loc[mask, r.column].head(5).map(lambda v: "<null>" if pd.isna(v) else str(v)).tolist() if (bad and r.column) else []
        results.append({"rule_id": r.rule_id, "severity": r.severity, "passed": bad == 0,
                        "failed_rows": bad, "examples": ex})
    return results
