import pathlib

import pandas as pd

from dq_rules_agent import profile_dataframe, suggest_rules, validate
from dq_rules_agent.exporters import to_great_expectations, to_pandera, to_sql

EX = pathlib.Path(__file__).resolve().parents[1] / "examples"


def _rules():
    base = pd.read_csv(EX / "customers.csv")
    return base, suggest_rules(profile_dataframe(base))


def test_rules_pass_on_the_data_they_came_from():
    base, rules = _rules()
    assert all(r["passed"] for r in validate(base, rules))


def test_planted_issues_are_caught():
    _, rules = _rules()
    new = pd.read_csv(EX / "customers_new_batch.csv")
    failed = {r["rule_id"] for r in validate(new, rules) if not r["passed"]}
    expected = {
        "customer_id.unique", "email.not_null", "email.pattern_email", "signup_date.type",
        "city.allowed_values", "postal_code.pattern_ca_postal_code", "plan.allowed_values",
        "monthly_spend.non_negative", "monthly_spend.expected_range", "orders_last_90d.non_negative",
    }
    assert expected <= failed


def test_expected_rule_types():
    _, rules = _rules()
    ids = {r.rule_id for r in rules}
    assert {"customer_id.not_null", "customer_id.unique", "email.pattern_email",
            "plan.allowed_values", "monthly_spend.max_null_rate"} <= ids
    assert "signup_date.unique" not in ids  # dates are not keys


def test_exports_render():
    _, rules = _rules()
    suite = to_great_expectations(rules)
    assert suite["expectations"] and all("expectation_type" in e for e in suite["expectations"])
    assert "pa.DataFrameSchema" in to_pandera(rules)
    assert to_sql(rules, "customers").count("SELECT") >= len(rules) - 2
