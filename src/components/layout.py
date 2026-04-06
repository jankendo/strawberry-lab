"""Shared layout helpers for consistent UX."""

from __future__ import annotations

import streamlit as st


def inject_app_style() -> None:
    """Inject lightweight shared CSS for page rhythm and section readability."""
    st.markdown(
        """
        <style>
        .sl-page-header h1 {
            margin-bottom: 0.2rem;
            font-size: 2rem;
        }
        .sl-page-header p {
            margin-top: 0;
            color: #555;
        }
        .sl-section-title {
            margin-top: 0.4rem;
            margin-bottom: 0.3rem;
            font-size: 1.15rem;
            font-weight: 600;
        }
        .sl-muted {
            color: #666;
            font-size: 0.9rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_page_header(title: str, description: str) -> None:
    """Render consistent page title block."""
    st.markdown(
        f"""
        <div class="sl-page-header">
          <h1>{title}</h1>
          <p>{description}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_section_title(title: str, description: str | None = None) -> None:
    """Render section heading and optional supporting text."""
    st.markdown(f'<div class="sl-section-title">{title}</div>', unsafe_allow_html=True)
    if description:
        st.markdown(f'<div class="sl-muted">{description}</div>', unsafe_allow_html=True)
