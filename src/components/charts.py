"""Chart rendering components."""

from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.constants.ui import EMPTY_STATE_MESSAGE


def render_plotly_chart(fig: go.Figure, key: str | None = None) -> None:
    """Render plotly chart consistently."""
    st.plotly_chart(fig, use_container_width=True, key=key)


def render_ranking_chart(rows: list[dict]) -> None:
    """Render ranking bar chart."""
    if not rows:
        st.info(EMPTY_STATE_MESSAGE)
        return
    fig = px.bar(rows, x="name", y="avg_overall", hover_data=["review_count"])
    render_plotly_chart(fig, key="ranking_chart")
