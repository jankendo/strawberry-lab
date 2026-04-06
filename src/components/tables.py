"""Table rendering helpers."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.constants.ui import EMPTY_STATE_MESSAGE


def render_table(data: list[dict], *, use_container_width: bool = True) -> None:
    """Render data table with consistent empty-state handling."""
    if not data:
        st.info(EMPTY_STATE_MESSAGE)
        return
    st.dataframe(pd.DataFrame(data), use_container_width=use_container_width, hide_index=True)
