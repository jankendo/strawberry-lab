"""Sidebar and primary navigation components."""

from __future__ import annotations

import streamlit as st

from src.constants.ui import APP_NAME
from src.services.auth_service import logout_user

_NAV_ITEMS: list[tuple[str, str, str, str]] = [
    ("dashboard", "Home.py", "ダッシュボード", "🏠"),
    ("varieties", "pages/01_varieties.py", "品種管理", "🍓"),
    ("reviews", "pages/02_reviews.py", "試食評価", "📝"),
    ("analytics", "pages/03_analytics.py", "分析", "📊"),
    ("pedigree", "pages/04_pedigree.py", "交配図", "🧬"),
    ("notes", "pages/06_notes.py", "研究メモ", "📓"),
    ("settings", "pages/07_settings.py", "設定", "⚙️"),
]


def _render_nav_button(page_key: str, page_path: str, page_label: str, page_icon: str, *, active_page: str) -> None:
    if page_key == active_page:
        st.markdown(
            f'<div class="sl-mobile-nav-active">{page_icon} {page_label}</div>',
            unsafe_allow_html=True,
        )
        return
    if st.button(
        f"{page_icon} {page_label}",
        key=f"top_nav_{active_page}_{page_key}",
        use_container_width=True,
        type="secondary",
    ):
        st.switch_page(page_path)


def render_primary_nav(*, active_page: str) -> None:
    """Render in-page primary navigation used for mobile-first operation."""
    if not st.session_state.get("is_authenticated"):
        return

    with st.container(border=True):
        st.caption("主要ナビゲーション")
        first_row = _NAV_ITEMS[:4]
        second_row = _NAV_ITEMS[4:]
        for row in (first_row, second_row):
            cols = st.columns(len(row), gap="small")
            for col, (page_key, page_path, page_label, page_icon) in zip(cols, row, strict=True):
                with col:
                    _render_nav_button(page_key, page_path, page_label, page_icon, active_page=active_page)


def render_sidebar(*, active_page: str) -> None:
    """Render desktop sidebar with explicit active navigation state."""
    with st.sidebar:
        st.markdown(
            f"""
            <div class="sl-sidebar-brand">
              <div class="sl-sidebar-brand-sub">テーマ</div>
              <div class="sl-sidebar-brand-title">🍓 イチゴ研究所</div>
              <div class="sl-sidebar-brand-sub">{APP_NAME}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.caption("ナビゲーション")
        for page_key, page_path, page_label, page_icon in _NAV_ITEMS:
            if page_key == active_page:
                st.markdown(
                    f'<div class="sl-sidebar-active">{page_icon} {page_label}</div>',
                    unsafe_allow_html=True,
                )
                continue
            st.page_link(page_path, label=f"{page_icon} {page_label}", use_container_width=True)

        with st.container(border=True):
            user = st.session_state.get("current_user")
            st.caption(f"ログイン中: {(user or {}).get('email', '-')}")
            if st.button("ログアウト", use_container_width=True, type="secondary", key="sidebar_logout"):
                logout_user()
