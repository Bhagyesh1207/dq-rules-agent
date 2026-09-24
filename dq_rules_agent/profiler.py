"""Column profiling. Pure pandas, no external services."""
from __future__ import annotations

import re
import warnings
from typing import Any

import pandas as pd

# Named patterns the profiler checks string columns against.
PATTERNS: dict[str, str] = {
    "email": r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$",
    "iso_date": r"^\d{4}-\d{2}-\d{2}$",
    "phone_na": r"^\+?1?[\s.-]?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}$",
    "ca_postal_code": r"^[A-Za-z]\d[A-Za-z][ -]?\d[A-Za-z]\d$",
    "us_zip": r"^\d{5}(-\d{4})?$",
    "uuid": r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
    "numeric_id": r"^\d+$",
    "alnum_code": r"^[A-Z]{2,5}-?\d{2,8}$",
}


def _infer_kind(s: pd.Series) -> str:
    non_null = s.dropna()
    if pd.api.types.is_bool_dtype(s):
        return "boolean"
    if pd.api.types.is_integer_dtype(s):
        return "integer"
    if pd.api.types.is_float_dtype(s):
        if len(non_null) and (non_null % 1 == 0).all():
            return "integer"
        return "float"
    if pd.api.types.is_datetime64_any_dtype(s):
        return "datetime"
    if len(non_null) == 0:
        return "empty"
    as_str = non_null.astype(str).str.strip()
    num = pd.to_numeric(as_str, errors="coerce")
    if num.notna().mean() >= 0.98:
        return "integer" if (num.dropna() % 1 == 0).all() else "float"
    if as_str.str.lower().isin(["true", "false", "yes", "no", "0", "1", "y", "n"]).all():
        return "boolean"
    if as_str.str.match(r"^\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}").mean() >= 0.98:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            dt = pd.to_datetime(as_str, errors="coerce", format="mixed")
        if dt.notna().mean() >= 0.98:
            return "datetime"
    return "string"


def _pattern_matches(values: pd.Series) -> dict[str, float]:
    out = {}
    for name, rx in PATTERNS.items():
        rate = values.str.match(re.compile(rx)).mean()
        if rate > 0:
            out[name] = round(float(rate), 4)
    return out


def profile_column(s: pd.Series) -> dict[str, Any]:
    n = len(s)
    non_null = s.dropna()
    if s.dtype == object:
        # treat blank strings as missing for profiling purposes
        blank = non_null.astype(str).str.strip() == ""
        non_null = non_null[~blank]
    kind = _infer_kind(non_null if len(non_null) else s)
    p: dict[str, Any] = {
        "name": s.name,
        "kind": kind,
        "rows": n,
        "null_count": int(n - len(non_null)),
        "null_rate": round(float((n - len(non_null)) / n), 4) if n else 0.0,
        "distinct": int(non_null.nunique()),
        "unique_rate": round(float(non_null.nunique() / len(non_null)), 4) if len(non_null) else 0.0,
    }
    if kind in ("integer", "float") and len(non_null):
        num = pd.to_numeric(non_null, errors="coerce").dropna()
        q = num.quantile([0.01, 0.25, 0.5, 0.75, 0.99])
        iqr = q[0.75] - q[0.25]
        p.update(
            min=float(num.min()), max=float(num.max()), mean=round(float(num.mean()), 4),
            std=round(float(num.std(ddof=0)), 4), p01=float(q[0.01]), p25=float(q[0.25]),
            median=float(q[0.5]), p75=float(q[0.75]), p99=float(q[0.99]),
            negative_count=int((num < 0).sum()), zero_count=int((num == 0).sum()),
            outlier_count=int(((num < q[0.25] - 1.5 * iqr) | (num > q[0.75] + 1.5 * iqr)).sum()),
        )
    if kind == "datetime" and len(non_null):
        dt = pd.to_datetime(non_null.astype(str), errors="coerce", format="mixed").dropna()
        if len(dt):
            p.update(min=str(dt.min().date()), max=str(dt.max().date()))
    if kind in ("string", "boolean") and len(non_null):
        vals = non_null.astype(str).str.strip()
        lens = vals.str.len()
        p.update(min_length=int(lens.min()), max_length=int(lens.max()))
        p["patterns"] = _pattern_matches(vals)
        p["has_leading_trailing_space"] = int((non_null.astype(str) != vals).sum())
        top = vals.value_counts().head(20)
        p["top_values"] = {str(k): int(v) for k, v in top.items()}
    return p


def profile_dataframe(df: pd.DataFrame) -> dict[str, Any]:
    return {
        "row_count": int(len(df)),
        "column_count": int(df.shape[1]),
        "duplicate_rows": int(df.duplicated().sum()),
        "columns": [profile_column(df[c]) for c in df.columns],
    }
