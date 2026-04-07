"""Application configuration helpers."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import streamlit as st


@dataclass(frozen=True)
class AppConfig:
    """Runtime settings loaded from Streamlit secrets or environment variables."""

    supabase_url: str
    supabase_anon_key: str
    github_token: str | None
    github_owner: str | None
    github_repo: str | None
    github_workflow_file: str
    github_ref: str
    app_timezone: str


def _get_setting(key: str, default: str | None = None) -> str | None:
    secrets: dict[str, Any] = dict(st.secrets) if hasattr(st, "secrets") else {}
    return secrets.get(key) or os.getenv(key) or default


def get_config() -> AppConfig:
    """Load validated application configuration."""
    supabase_url = _get_setting("SUPABASE_URL")
    supabase_anon_key = _get_setting("SUPABASE_ANON_KEY")
    app_timezone = _get_setting("APP_TIMEZONE", "Asia/Tokyo")
    if not supabase_url or not supabase_anon_key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_ANON_KEY are required.")
    return AppConfig(
        supabase_url=supabase_url,
        supabase_anon_key=supabase_anon_key,
        github_token=_get_setting("GITHUB_TOKEN"),
        github_owner=_get_setting("GITHUB_OWNER"),
        github_repo=_get_setting("GITHUB_REPO"),
        github_workflow_file=_get_setting("GITHUB_WORKFLOW_FILE", "scrape.yml") or "scrape.yml",
        github_ref=_get_setting("GITHUB_REF", "main") or "main",
        app_timezone=app_timezone or "Asia/Tokyo",
    )
