# Data quality rules report

Rows: 500 | Columns: 9 | Duplicate rows: 0 | Rules suggested: 33

## Column profile

| column | type | null % | distinct | range / top pattern |
|---|---|---|---|---|
| customer_id | string | 0.0% | 500 | alnum_code (100%) |
| email | string | 0.0% | 500 | email (100%) |
| signup_date | datetime | 0.0% | 500 | 2024-01-01 to 2025-05-14 |
| city | string | 0.0% | 6 |  |
| postal_code | string | 0.0% | 500 | ca_postal_code (100%) |
| plan | string | 0.0% | 3 |  |
| monthly_spend | float | 2.4% | 471 | 3.5 to 182.84 |
| orders_last_90d | integer | 0.0% | 16 | 0.0 to 15.0 |
| is_active | boolean | 0.0% | 2 |  |

## Suggested rules

| rule | severity | confidence | why | result |
|---|---|---|---|---|
| `table.row_count` | warning | 100% | Current load has 500 rows; flag loads under half or over double that. | pass |
| `table.no_duplicate_rows` | error | 100% | 0 fully duplicated rows found. | pass |
| `customer_id.not_null` | error | 100% | 0 of 500 rows are null. | pass |
| `customer_id.unique` | error | 100% | All 500 non-null values are distinct and the name looks like a key. | pass |
| `customer_id.pattern_alnum_code` | error | 100% | 100.0% of values match the alnum_code pattern. | pass |
| `customer_id.fixed_length` | warning | 100% | Every value is exactly 11 characters. | pass |
| `email.not_null` | error | 100% | 0 of 500 rows are null. | pass |
| `email.unique` | error | 100% | All 500 non-null values are distinct. | pass |
| `email.pattern_email` | error | 100% | 100.0% of values match the email pattern. | pass |
| `signup_date.not_null` | error | 100% | 0 of 500 rows are null. | pass |
| `signup_date.type` | error | 100% | Profiler inferred 'datetime' for all non-null values. | pass |
| `signup_date.not_in_future` | error | 100% | Latest value is 2025-05-14; no future dates seen. | pass |
| `signup_date.date_floor` | warning | 100% | Earliest value is 2024-01-01. | pass |
| `city.not_null` | error | 100% | 0 of 500 rows are null. | pass |
| `city.allowed_values` | error | 100% | Only 6 distinct values in 500 rows; treat as a closed list. | pass |
| `city.length` | warning | 100% | Lengths range from 7 to 11. | pass |
| `postal_code.not_null` | error | 100% | 0 of 500 rows are null. | pass |
| `postal_code.unique` | error | 100% | All 500 non-null values are distinct and the name looks like a key. | pass |
| `postal_code.pattern_ca_postal_code` | error | 100% | 100.0% of values match the ca_postal_code pattern. | pass |
| `postal_code.fixed_length` | warning | 100% | Every value is exactly 7 characters. | pass |
| `plan.not_null` | error | 100% | 0 of 500 rows are null. | pass |
| `plan.allowed_values` | error | 100% | Only 3 distinct values in 500 rows; treat as a closed list. | pass |
| `plan.length` | warning | 100% | Lengths range from 3 to 5. | pass |
| `monthly_spend.max_null_rate` | warning | 100% | 2.4% null today; alert if it rises above 4%. | pass |
| `monthly_spend.type` | error | 100% | Profiler inferred 'float' for all non-null values. | pass |
| `monthly_spend.non_negative` | error | 100% | No negative values across 488 rows (min 3.5). | pass |
| `monthly_spend.expected_range` | warning | 100% | Observed 3.5 to 182.84 (median 55.16, 9 IQR outliers). Values outside 0 to 300 need review. | pass |
| `orders_last_90d.not_null` | error | 100% | 0 of 500 rows are null. | pass |
| `orders_last_90d.type` | error | 100% | Profiler inferred 'integer' for all non-null values. | pass |
| `orders_last_90d.non_negative` | error | 100% | No negative values across 500 rows (min 0). | pass |
| `orders_last_90d.expected_range` | warning | 100% | Observed 0 to 15 (median 6, 9 IQR outliers). Values outside 0 to 20 need review. | pass |
| `is_active.not_null` | error | 100% | 0 of 500 rows are null. | pass |
| `is_active.type` | error | 100% | Profiler inferred 'boolean' for all non-null values. | pass |
