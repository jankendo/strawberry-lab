"""Shared layout helpers for consistent UX."""

from __future__ import annotations

import streamlit as st


def inject_app_style() -> None:
    """Inject shared production-like CSS for Japanese-first UI."""
    st.markdown(
        """
        <style>
        html, body, [class*="css"], [data-testid="stAppViewContainer"] {
            font-family: "Noto Sans JP", "Hiragino Kaku Gothic ProN", "Yu Gothic UI",
                         "Meiryo", "Segoe UI", sans-serif;
        }
        .block-container {
            padding-top: 1rem;
            padding-bottom: 2.5rem;
            max-width: 1240px;
        }
        [data-testid="stAppViewContainer"] {
            background: linear-gradient(180deg, #fff8fa 0%, #ffffff 280px);
        }
        div[data-testid="stToolbar"] {
            right: 0.8rem;
        }
        .sl-page-header h1 {
            margin-bottom: 0.2rem;
            font-size: 2.05rem;
            letter-spacing: 0.02em;
            color: #7a1236;
        }
        .sl-page-header p {
            margin-top: 0;
            color: #5d4d53;
            line-height: 1.65;
        }
        .sl-page-lead {
            margin-top: 0.6rem;
            margin-bottom: 1rem;
            color: #5c4850;
            font-size: 0.95rem;
            line-height: 1.6;
            background: #fff;
            border: 1px solid #f0dfe5;
            border-radius: 12px;
            padding: 0.75rem 0.9rem;
        }
        .sl-section-title {
            margin-top: 0.95rem;
            margin-bottom: 0.35rem;
            font-size: 1.15rem;
            font-weight: 600;
            border-left: 4px solid #d61f53;
            padding-left: 0.5rem;
        }
        .sl-muted {
            color: #68565d;
            font-size: 0.9rem;
            line-height: 1.5;
        }
        .sl-kpi-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
            gap: 10px;
            margin: 0.35rem 0 0.9rem;
        }
        .sl-kpi-card {
            background: #fff;
            border: 1px solid #f0d7df;
            border-radius: 12px;
            padding: 0.75rem 0.9rem;
            box-shadow: 0 4px 16px rgba(118, 35, 64, 0.05);
        }
        .sl-kpi-label {
            font-size: 0.82rem;
            color: #6f5a62;
            margin-bottom: 0.2rem;
        }
        .sl-kpi-value {
            font-size: 1.35rem;
            font-weight: 700;
            color: #7a1236;
            line-height: 1.2;
        }
        .sl-kpi-sub {
            margin-top: 0.1rem;
            color: #7a6a70;
            font-size: 0.75rem;
        }
        .sl-info-card {
            background: #ffffff;
            border: 1px solid #f0d7df;
            border-radius: 12px;
            padding: 0.8rem 0.95rem;
            margin-bottom: 0.7rem;
            box-shadow: 0 4px 16px rgba(118, 35, 64, 0.04);
        }
        .sl-info-card strong {
            color: #7a1236;
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


def render_lead(text: str) -> None:
    """Render highlighted lead paragraph."""
    st.markdown(f'<div class="sl-page-lead">{text}</div>', unsafe_allow_html=True)


def render_section_title(title: str, description: str | None = None) -> None:
    """Render section heading and optional supporting text."""
    st.markdown(f'<div class="sl-section-title">{title}</div>', unsafe_allow_html=True)
    if description:
        st.markdown(f'<div class="sl-muted">{description}</div>', unsafe_allow_html=True)


def render_kpi_cards(items: list[tuple[str, str, str | None]]) -> None:
    """Render compact KPI cards."""
    cards_html = []
    for label, value, sub_text in items:
        sub = f'<div class="sl-kpi-sub">{sub_text}</div>' if sub_text else ""
        cards_html.append(
            f"""
            <div class="sl-kpi-card">
              <div class="sl-kpi-label">{label}</div>
              <div class="sl-kpi-value">{value}</div>
              {sub}
            </div>
            """
        )
    st.markdown(f'<div class="sl-kpi-grid">{"".join(cards_html)}</div>', unsafe_allow_html=True)


def render_info_card(text: str) -> None:
    """Render informational card block."""
    st.markdown(f'<div class="sl-info-card">{text}</div>', unsafe_allow_html=True)
