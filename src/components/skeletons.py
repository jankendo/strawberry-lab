"""Reusable loading skeletons for heavy dashboard sections."""

from __future__ import annotations

from html import escape

import streamlit as st

from src.components.tables import is_mobile_client

_SKELETON_STYLE_KEY = "_sl_skeleton_style_injected"


def _coerce_int(value: int, *, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, int(value)))


def _resolve_mobile(is_mobile: bool | None) -> bool:
    return is_mobile if is_mobile is not None else is_mobile_client()


def _inject_style() -> None:
    try:
        if st.session_state.get(_SKELETON_STYLE_KEY):
            return
    except Exception:
        pass

    st.markdown(
        """
        <style>
        @keyframes sl-skeleton-shimmer {
            0% { background-position: 120% 0; }
            100% { background-position: -120% 0; }
        }

        .sl-skeleton-scope {
            --sl-skeleton-base: #e6ebf3;
            --sl-skeleton-highlight: #f7f9fc;
            --sl-skeleton-border: #d8dfeb;
        }
        .sl-skeleton-line {
            display: block;
            height: 0.74rem;
            border-radius: 999px;
            background: linear-gradient(
                110deg,
                var(--sl-skeleton-base) 26%,
                var(--sl-skeleton-highlight) 46%,
                var(--sl-skeleton-base) 66%
            );
            background-size: 220% 100%;
            animation: sl-skeleton-shimmer 1.2s linear infinite;
        }
        .sl-skeleton-line + .sl-skeleton-line {
            margin-top: 0.52rem;
        }
        .sl-skeleton-card-grid {
            display: grid;
            gap: 0.72rem;
        }
        .sl-skeleton-card-grid[data-mobile="false"] {
            grid-template-columns: repeat(3, minmax(0, 1fr));
        }
        .sl-skeleton-card-grid[data-mobile="true"] {
            grid-template-columns: minmax(0, 1fr);
        }
        .sl-skeleton-card,
        .sl-skeleton-list-item,
        .sl-skeleton-table,
        .sl-skeleton-chart {
            background: #ffffff;
            border: 1px solid var(--sl-skeleton-border);
            border-radius: 12px;
            padding: 0.85rem 0.95rem;
        }
        .sl-skeleton-list-item + .sl-skeleton-list-item {
            margin-top: 0.62rem;
        }
        .sl-skeleton-table-head,
        .sl-skeleton-table-row {
            display: grid;
            grid-template-columns: repeat(var(--sl-skeleton-columns), minmax(0, 1fr));
            gap: 0.55rem;
        }
        .sl-skeleton-table-head {
            margin-bottom: 0.62rem;
        }
        .sl-skeleton-table-row + .sl-skeleton-table-row {
            margin-top: 0.52rem;
        }
        .sl-skeleton-chart-canvas {
            margin-top: 0.72rem;
            height: var(--sl-skeleton-chart-height);
            border-radius: 10px;
            border: 1px solid #e6ebf3;
            background: linear-gradient(180deg, #ffffff 0%, #f5f7fb 100%);
            display: flex;
            align-items: flex-end;
            gap: 0.35rem;
            padding: 0.6rem 0.5rem;
        }
        .sl-skeleton-chart-bar {
            flex: 1 1 0;
            border-radius: 6px 6px 4px 4px;
            background: linear-gradient(
                110deg,
                var(--sl-skeleton-base) 26%,
                var(--sl-skeleton-highlight) 46%,
                var(--sl-skeleton-base) 66%
            );
            background-size: 220% 100%;
            animation: sl-skeleton-shimmer 1.2s linear infinite;
        }
        @media (max-width: 880px) {
            .sl-skeleton-card-grid[data-mobile="false"] {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    try:
        st.session_state[_SKELETON_STYLE_KEY] = True
    except Exception:
        pass


def _line(width: str) -> str:
    return f'<span class="sl-skeleton-line" style="width: {escape(width)};"></span>'


def render_card_skeleton(count: int = 3, *, is_mobile: bool | None = None) -> None:
    """Render KPI/card-like placeholders."""
    _inject_style()
    mobile = _resolve_mobile(is_mobile)
    card_count = _coerce_int(count, minimum=1, maximum=10)
    cards = "".join(
        (
            '<div class="sl-skeleton-card">'
            f"{_line('44%')}{_line('76%')}{_line('55%')}"
            "</div>"
        )
        for _ in range(card_count)
    )
    st.markdown(
        (
            '<div class="sl-skeleton-scope">'
            f'<div class="sl-skeleton-card-grid" data-mobile="{str(mobile).lower()}">{cards}</div>'
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def render_list_skeleton(rows: int = 4, *, is_mobile: bool | None = None) -> None:
    """Render card-list placeholders."""
    _inject_style()
    _ = _resolve_mobile(is_mobile)
    row_count = _coerce_int(rows, minimum=1, maximum=14)
    items = "".join(
        (
            '<div class="sl-skeleton-list-item">'
            f"{_line('52%')}{_line('34%')}{_line('78%')}"
            "</div>"
        )
        for _ in range(row_count)
    )
    st.markdown(f'<div class="sl-skeleton-scope">{items}</div>', unsafe_allow_html=True)


def render_table_skeleton(rows: int = 5, columns: int = 4, *, is_mobile: bool | None = None) -> None:
    """Render table placeholders (mobile falls back to list placeholders)."""
    mobile = _resolve_mobile(is_mobile)
    if mobile:
        render_list_skeleton(rows=max(rows, 3), is_mobile=True)
        return

    _inject_style()
    row_count = _coerce_int(rows, minimum=1, maximum=16)
    column_count = _coerce_int(columns, minimum=2, maximum=8)
    header = "".join(_line("72%") for _ in range(column_count))
    body = "".join(
        (
            f'<div class="sl-skeleton-table-row" style="--sl-skeleton-columns: {column_count};">'
            + "".join(_line("88%") for _ in range(column_count))
            + "</div>"
        )
        for _ in range(row_count)
    )
    st.markdown(
        (
            '<div class="sl-skeleton-scope">'
            '<div class="sl-skeleton-table">'
            f'<div class="sl-skeleton-table-head" style="--sl-skeleton-columns: {column_count};">{header}</div>'
            f"{body}"
            "</div>"
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def render_chart_skeleton(*, height: int | None = None, is_mobile: bool | None = None) -> None:
    """Render chart placeholders."""
    _inject_style()
    mobile = _resolve_mobile(is_mobile)
    chart_height = _coerce_int(height or (220 if mobile else 320), minimum=160, maximum=520)
    bar_levels = [34, 48, 62, 44, 70, 52, 78, 64] if not mobile else [38, 56, 42, 68, 54, 72]
    bars = "".join(
        f'<span class="sl-skeleton-chart-bar" style="height: {level}%;"></span>'
        for level in bar_levels
    )
    st.markdown(
        (
            '<div class="sl-skeleton-scope">'
            '<div class="sl-skeleton-chart">'
            f"{_line('38%')}{_line('64%')}"
            f'<div class="sl-skeleton-chart-canvas" style="--sl-skeleton-chart-height: {chart_height}px;">{bars}</div>'
            "</div>"
            "</div>"
        ),
        unsafe_allow_html=True,
    )
