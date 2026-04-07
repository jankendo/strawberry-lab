"""Supabase client creation helpers."""

from __future__ import annotations

import streamlit as st
from supabase import Client, create_client

from src.config import get_config


@st.cache_resource
def get_anon_supabase_client() -> Client:
    """Create a Supabase client with the anon key."""
    cfg = get_config()
    return create_client(cfg.supabase_url, cfg.supabase_anon_key)


@st.cache_resource
def get_service_role_supabase_client() -> Client | None:
    """Create a Supabase client with the service-role key when configured."""
    cfg = get_config()
    if not cfg.supabase_service_role_key:
        return None
    return create_client(cfg.supabase_url, cfg.supabase_service_role_key)


def get_app_supabase_client() -> Client:
    """Return the best available app client for public-mode access."""
    return get_service_role_supabase_client() or get_anon_supabase_client()


def get_session_supabase_client(access_token: str, refresh_token: str) -> Client:
    """Create a user-authenticated Supabase client from session tokens."""
    client = get_anon_supabase_client()
    client.auth.set_session(access_token, refresh_token)
    return client
