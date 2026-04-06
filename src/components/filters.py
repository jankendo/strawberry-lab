"""Reusable filters for list pages."""

from __future__ import annotations

from datetime import date, timedelta

import streamlit as st


def render_date_range_filter(key_prefix: str, default_months: int = 12) -> tuple[date, date]:
    """Render date range controls."""
    end = date.today()
    start = end - timedelta(days=default_months * 30)
    col1, col2 = st.columns(2)
    with col1:
        from_date = st.date_input("開始日", value=start, key=f"{key_prefix}_from_date")
    with col2:
        to_date = st.date_input("終了日", value=end, key=f"{key_prefix}_to_date")
    return from_date, to_date
