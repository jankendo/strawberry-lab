"""Sidebar UI component."""

from __future__ import annotations

import streamlit as st

from src.constants.ui import APP_NAME
from src.services.auth_service import logout_user


def render_sidebar() -> None:
    """Render common sidebar with current user and logout."""
    with st.sidebar:
        st.title(APP_NAME)
        user = st.session_state.get("current_user")
        if user:
            st.caption(f"ログイン中: {user.get('email', '-')}")
            if st.button("ログアウト", use_container_width=True):
                logout_user()
