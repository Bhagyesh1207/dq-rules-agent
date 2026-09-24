"""Command line entry point.

    dq-rules suggest data.csv --out rules_out/
    dq-rules validate new_data.csv --rules rules_out/rules.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

import pandas as pd

from . import exporters
from .profiler import profile_dataframe
from .rules import Rule, suggest_rules
from .validator import validate


def _read(path: str) -> pd.DataFrame:
    p = pathlib.Path(path)
    if p.suffix.lower() in (".parquet", ".pq"):
        return pd.read_parquet(p)
    if p.suffix.lower() in (".xlsx", ".xls"):
        return pd.read_excel(p)
    return pd.read_csv(p)


def cmd_suggest(a) -> int:
    df = _read(a.data)
    prof = profile_dataframe(df)
    rules = suggest_rules(prof)
    results = validate(df, rules)
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    table = a.table or pathlib.Path(a.data).stem
    (out / "profile.json").write_text(json.dumps(prof, indent=2, default=str))
    (out / "rules.json").write_text(exporters.to_json(rules))
    (out / "great_expectations_suite.json").write_text(
        json.dumps(exporters.to_great_expectations(rules, f"{table}_suite"), indent=2))
    (out / "pandera_schema.py").write_text(exporters.to_pandera(rules))
    (out / "checks.sql").write_text(exporters.to_sql(rules, table))
    (out / "report.md").write_text(exporters.to_markdown(prof, rules, results))
    failed = [r for r in results if not r["passed"]]
    print(f"Profiled {prof['row_count']} rows x {prof['column_count']} columns")
    print(f"Suggested {len(rules)} rules -> {out}/")
    print(f"On this data: {len(results) - len(failed)} pass, {len(failed)} flag rows for review")
    return 0


def cmd_validate(a) -> int:
    df = _read(a.data)
    rules = [Rule(**r) for r in json.loads(pathlib.Path(a.rules).read_text())]
    results = validate(df, rules)
    errors = 0
    for r in results:
        mark = "PASS" if r["passed"] else "FAIL"
        if not r["passed"] and r["severity"] == "error":
            errors += 1
        line = f"{mark:4}  {r['rule_id']:<40} {r['severity']:<8}"
        if not r["passed"]:
            line += f" {r['failed_rows']} rows, e.g. {r['examples'][:3]}"
        print(line)
    print(f"\n{sum(r['passed'] for r in results)}/{len(results)} rules passed, {errors} error-level failures")
    return 1 if errors else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="dq-rules", description="Profile data and generate data quality rules.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("suggest", help="profile a dataset and write rules + exports")
    s.add_argument("data")
    s.add_argument("--out", default="dq_rules_out")
    s.add_argument("--table", help="table name used in the SQL export")
    s.set_defaults(fn=cmd_suggest)
    v = sub.add_parser("validate", help="run a rules.json file against a dataset")
    v.add_argument("data")
    v.add_argument("--rules", required=True)
    v.set_defaults(fn=cmd_validate)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
