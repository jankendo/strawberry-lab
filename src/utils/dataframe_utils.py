"""DataFrame formatting helpers for exports."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from src.utils.date_utils import to_jst_iso8601


def serialize_array(value: object) -> str:
    """Serialize arrays using pipe separator."""
    if isinstance(value, list):
        return "|".join(str(item) for item in value)
    return "" if value is None else str(value)


def format_export_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize dataframe fields for CSV export."""
    out = df.copy()
    for column in out.columns:
        out[column] = out[column].map(
            lambda v: to_jst_iso8601(v) if isinstance(v, datetime) else serialize_array(v)
        )
    return out
