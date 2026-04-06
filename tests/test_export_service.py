from datetime import UTC, datetime

import pandas as pd

from src.utils.dataframe_utils import format_export_dataframe


def test_export_format_converts_arrays_and_timestamps() -> None:
    df = pd.DataFrame(
        [
            {
                "tags": ["a", "b"],
                "created_at": datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
            }
        ]
    )
    formatted = format_export_dataframe(df)
    assert formatted.iloc[0]["tags"] == "a|b"
    assert "+09:00" in formatted.iloc[0]["created_at"]


def test_csv_uses_bom_prefix() -> None:
    csv = ("\ufeff" + pd.DataFrame([{"x": 1}]).to_csv(index=False)).encode("utf-8")
    assert csv.startswith(b"\xef\xbb\xbf")
