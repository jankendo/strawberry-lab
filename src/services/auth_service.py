"""Authentication and authorization service."""

from __future__ import annotations

import streamlit as st

from src.core.supabase_client import get_anon_supabase_client


AUTH_KEYS = ("current_user", "supabase_client_user", "is_authenticated", "access_token", "refresh_token")


def initialize_auth_state() -> None:
    """Initialize auth session state keys."""
    for key in AUTH_KEYS:
        if key not in st.session_state:
            st.session_state[key] = None if key != "is_authenticated" else False


def login_user(email: str, password: str) -> None:
    """Login with Supabase Auth and enforce app_users admin membership."""
    initialize_auth_state()
    client = get_anon_supabase_client()
    result = client.auth.sign_in_with_password({"email": email, "password": password})
    if not result.user or not result.session:
        raise RuntimeError("ログインに失敗しました。")
    admin = (
        client.table("app_users")
        .select("user_id,email,role")
        .eq("user_id", result.user.id)
        .eq("role", "admin")
        .maybe_single()
        .execute()
    )
    if not admin.data:
        client.auth.sign_out()
        raise PermissionError("このアカウントは許可されていません。")
    st.session_state["current_user"] = {"id": result.user.id, "email": result.user.email}
    st.session_state["supabase_client_user"] = client
    st.session_state["is_authenticated"] = True
    st.session_state["access_token"] = result.session.access_token
    st.session_state["refresh_token"] = result.session.refresh_token


def logout_user() -> None:
    """Logout current user and clear auth-related session state."""
    client = st.session_state.get("supabase_client_user")
    if client:
        client.auth.sign_out()
    for key in AUTH_KEYS:
        st.session_state.pop(key, None)
    st.switch_page("Home.py")


def get_user_client():
    """Return authenticated user client from session."""
    return st.session_state.get("supabase_client_user")


def require_admin_session() -> None:
    """Guard protected pages and redirect to Home.py when unauthorized."""
    initialize_auth_state()
    if not st.session_state.get("is_authenticated") or not st.session_state.get("current_user"):
        st.switch_page("Home.py")
        st.stop()
    client = get_user_client()
    user_id = st.session_state["current_user"]["id"]
    admin = (
        client.table("app_users")
        .select("user_id")
        .eq("user_id", user_id)
        .eq("role", "admin")
        .maybe_single()
        .execute()
    )
    if not admin.data:
        logout_user()
        st.error("管理者権限がありません。")
        st.stop()
