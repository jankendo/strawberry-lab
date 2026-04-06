"""Pagination component utilities."""

from __future__ import annotations

import streamlit as st

from src.constants.ui import DEFAULT_PAGE_SIZE, PAGE_SIZE_OPTIONS


def render_pagination_controls(key_prefix: str) -> tuple[int, int]:
    """Render page size and page number controls and return them."""
    page_size_key = f"{key_prefix}_page_size"
    page_key = f"{key_prefix}_page"
    if page_size_key not in st.session_state:
        st.session_state[page_size_key] = DEFAULT_PAGE_SIZE
    if page_key not in st.session_state:
        st.session_state[page_key] = 1
    col1, col2 = st.columns([1, 1])
    with col1:
        st.session_state[page_size_key] = st.selectbox(
            "表示件数",
            options=PAGE_SIZE_OPTIONS,
            index=PAGE_SIZE_OPTIONS.index(st.session_state[page_size_key]),
            key=f"{key_prefix}_size_select",
        )
    with col2:
        st.session_state[page_key] = st.number_input(
            "ページ",
            min_value=1,
            value=st.session_state[page_key],
            step=1,
            key=f"{key_prefix}_page_input",
        )
    return int(st.session_state[page_key]), int(st.session_state[page_size_key])
