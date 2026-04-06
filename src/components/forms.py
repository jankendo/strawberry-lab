"""Form helper components."""

from __future__ import annotations

import streamlit as st

from src.utils.text_utils import split_dedup_values


def comma_values_input(label: str, key: str, max_items: int, max_length: int) -> list[str]:
    """Render comma-separated value input and return parsed values."""
    raw = st.text_input(label, key=key)
    try:
        return split_dedup_values(raw, max_items=max_items, max_length=max_length)
    except ValueError as exc:
        st.error(str(exc))
        return []
