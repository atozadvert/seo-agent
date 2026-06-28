from __future__ import annotations

import pandas as pd


def safe_int(value, default: int = 0) -> int:
    """Convert a value to an integer without crashing on decimal-like strings."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return default
    if pd.isna(value):
        return default
    try:
        text = str(value).strip().replace(",", "")
        if not text:
            return default
        numeric = pd.to_numeric(text, errors="coerce")
        if pd.isna(numeric):
            return default
        return int(round(float(numeric)))
    except Exception:
        return default


def safe_int_series(series, default: int = 0):
    """Coerce a pandas Series to nullable integers safely."""
    if series is None:
        return pd.Series(dtype="Int64")
    coerced = pd.to_numeric(series, errors="coerce").fillna(default)
    return coerced.round(0).astype("Int64")


def safe_float(value, default: float = 0.0) -> float:
    """Convert a value to a float without crashing on non-numeric strings."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return default
    if pd.isna(value):
        return default
    try:
        text = str(value).strip().replace(",", "")
        if not text:
            return default
        numeric = pd.to_numeric(text, errors="coerce")
        if pd.isna(numeric):
            return default
        return float(numeric)
    except Exception:
        return default
