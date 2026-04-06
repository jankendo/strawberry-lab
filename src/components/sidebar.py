"""Sidebar UI component."""

from __future__ import annotations

import streamlit as st

from src.constants.ui import APP_NAME
from src.services.auth_service import logout_user


def render_sidebar() -> None:
    """Render common sidebar with current user and logout."""
    with st.sidebar:
        st.markdown(
            f"""
            <div style="padding:8px 10px 10px 10px;border:1px solid #f0d7df;border-radius:12px;background:#fff;">
              <div style="font-size:0.78rem;color:#7a6a70;">テーマ</div>
              <div style="font-size:1.05rem;font-weight:700;color:#7a1236;">🍓 イチゴ研究所</div>
              <div style="margin-top:3px;font-size:0.8rem;color:#6f5a62;">{APP_NAME}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("##### ナビゲーション")
        st.page_link("Home.py", label="ダッシュボード")
        st.page_link("pages/01_varieties.py", label="品種管理")
        st.page_link("pages/02_reviews.py", label="試食評価")
        st.page_link("pages/03_analytics.py", label="分析")
        st.page_link("pages/04_pedigree.py", label="交配図")
        st.page_link("pages/06_notes.py", label="研究メモ")
        st.page_link("pages/07_settings.py", label="設定")
        st.divider()
        user = st.session_state.get("current_user")
        if user:
            st.caption(f"ログイン中: {user.get('email', '-')}")
            if st.button("ログアウト", use_container_width=True):
                logout_user()
