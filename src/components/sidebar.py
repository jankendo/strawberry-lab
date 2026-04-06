"""Sidebar UI component."""

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
]


def render_sidebar(*, active_page: str) -> None:
    """Render common sidebar with explicit active navigation state."""
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
            if active_page == "settings":
                st.markdown('<div class="sl-sidebar-active">⚙️ 設定</div>', unsafe_allow_html=True)
            else:
                st.page_link("pages/07_settings.py", label="⚙️ 設定", use_container_width=True)
            if st.button("ログアウト", use_container_width=True, type="secondary", key="sidebar_logout"):
                logout_user()
