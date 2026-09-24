# DQ Rules Agent

**Profile a dataset. Get data quality rules back, each with a reason. Export them as real checks.**

Live demo: **https://dq-rules-agent.vercel.app** (runs fully in your browser, your file never leaves your machine)

**No LLM, no API key.** Every rule is generated from the data's own statistics (null rates, distinct counts, ranges, value lists, text patterns), and every rule carries the reason it was suggested. Same input, same rules, every time, and it costs nothing to run.

Writing data quality rules by hand is slow, and most teams only add a rule after something breaks. DQ Rules Agent starts from the data you already trust: it profiles every column, reads the evidence (null rates, key-like columns, ranges, closed value lists, text patterns, lengths, stray whitespace) and turns it into a reviewable rule set. You keep the rules you agree with, export them to the tool your pipeline already uses, and run them on every new batch.

## What it does

1. **Profile**: per-column type inference, null rate, distinct count, min/max/percentiles, IQR outliers, top values, string lengths, and matches against common patterns (email, ISO date, Canadian postal code, US zip, phone, UUID, codes like `CUST-100231`).
2. **Suggest rules**: each rule has a severity (`error` or `warning`), a confidence score and a plain-English rationale tied to the profile, for example:
   - `customer_id.unique` - "All 500 non-null values are distinct and the name looks like a key."
   - `plan.allowed_values` - "Only 3 distinct values in 500 rows; treat as a closed list."
   - `monthly_spend.max_null_rate` - "2.4% null today; alert if it rises above 4%."
3. **Export** the same rules to:
   - Great Expectations expectation suite (JSON)
   - pandera `DataFrameSchema` (Python)
   - SQL checks, one query per rule returning `failed_rows` (tested on DuckDB)
   - `rules.json` and a Markdown report
4. **Validate** a new batch against `rules.json` and see which rules fail, with example values.

## Example

The repo ships a 500-row sample (`examples/customers.csv`) and a "next day" batch with 10 planted problems (`examples/customers_new_batch.csv`).

```bash
pip install -e .
dq-rules suggest examples/customers.csv --out examples/output --table customers
# Profiled 500 rows x 9 columns
# Suggested 33 rules -> examples/output/
# On this data: 33 pass, 0 flag rows for review

dq-rules validate examples/customers_new_batch.csv --rules examples/output/rules.json
```

All 10 planted problems are caught:

| planted problem | caught by |
|---|---|
| duplicate customer ID | `customer_id.unique` |
| missing email | `email.not_null` |
| malformed email | `email.pattern_email` |
| impossible date (2031-02-30) | `signup_date.type` |
| " Toronto" with a leading space | `city.allowed_values` |
| US zip in a Canadian postal code column | `postal_code.pattern_ca_postal_code` |
| new plan value "enterprise" | `plan.allowed_values` |
| negative monthly spend | `monthly_spend.non_negative` |
| spend outlier (9999) | `monthly_spend.expected_range` |
| negative order count | `orders_last_90d.non_negative` |

The generated pandera schema and SQL checks flag the same rows. See [`examples/output/`](examples/output) for every generated file, including [`report.md`](examples/output/report.md).

Want to see it without installing anything? Run the same two files in the [live demo](https://dq-rules-agent.vercel.app).

## How it saves time

| | by hand | with DQ Rules Agent |
|---|---|---|
| first rule set for a new table | read the data, guess thresholds, write each check | generated from a profile in seconds, then reviewed |
| same rules in three tools | written three times (GE, pandera, SQL) | exported from one rule set |
| explaining a rule to a reviewer | tribal knowledge | the rationale is stored with the rule |
| new batch arrives | issues found downstream, in a dashboard or model | flagged at load time with example values |

Measured on a 2-vCPU cloud machine (Intel Xeon 2.6 GHz):

- 500 rows x 9 columns: profile + 33 rules in about 0.04 seconds
- 100,000 rows x 9 columns: profile + 32 rules in about 2.5 seconds, and validating all rules on those 100,000 rows took about 0.8 seconds

On the sample, the generated rules caught all 10 problems planted in the next batch (table above) without writing a single check by hand. The time a person still spends is review: keep, tighten or drop each suggested rule. That review is much faster than writing the rules from scratch, because each one arrives with the evidence behind it.

## Use it from Python

```python
import pandas as pd
from dq_rules_agent import profile_dataframe, suggest_rules, validate
from dq_rules_agent.exporters import to_great_expectations, to_sql

df = pd.read_csv("examples/customers.csv")
rules = suggest_rules(profile_dataframe(df))
results = validate(pd.read_csv("examples/customers_new_batch.csv"), rules)
print(to_sql(rules, table="customers"))
```

## How the rules are chosen

| evidence in the profile | rule suggested |
|---|---|
| no nulls | `not_null` (error) |
| up to 20% nulls | `max_null_rate` at 1.5x today's rate (warning) |
| 100% distinct and key-like name or email/UUID values | `unique` |
| numeric, never negative | `between min=0` (error) |
| numeric spread | `expected_range` with a 10% margin (warning) |
| 15 or fewer distinct strings | `allowed_values` closed list |
| 90%+ of values match a known pattern | `regex` (error at 99%+, else warning) |
| short strings | `length` bounds, or `fixed_length` |
| dates, none in the future | `not_in_future` and `date_floor` |
| values with leading/trailing spaces | `trimmed` (warning) |
| table level | `row_count` within 0.5x to 2x, `no_duplicate_rows` |

The logic is deterministic and runs offline. No API key or LLM is needed.

## Project layout

```
dq_rules_agent/
  profiler.py    column profiling (pandas only)
  rules.py       profile -> rules, with rationale and confidence
  validator.py   run rules on a DataFrame
  exporters.py   Great Expectations, pandera, SQL, Markdown, JSON
  cli.py         `dq-rules suggest` and `dq-rules validate`
demo/index.html  static browser demo (Pyodide runs the same Python package)
examples/        sample data and generated outputs
tests/           pytest suite
```

## Tests

```bash
pip install -e ".[dev]"
pytest
```

## Roadmap

- Optional LLM layer on top of the statistical engine: suggest semantic rules the numbers can't see (for example "discount must be less than price", or "province must match postal code"), and write business-friendly rule descriptions. Off by default and bring-your-own-key, so the core stays free and deterministic
- Cross-column rules (for example `end_date >= start_date`)
- Drift checks between batches (distribution shift, new categories)
- dbt tests export

## Author

Built by [Bhagyesh Patel](https://itsbhagyesh.vercel.app), Data Analyst working on data quality and validation.
