"""Read-only services for MAFF scrape runs and logs."""

from __future__ import annotations

import streamlit as st

from src.services.auth_service import get_user_client


@st.cache_data(ttl=300)
def get_recent_variety_scrape_runs(limit: int = 20) -> list[dict]:
    """Fetch recent MAFF variety scrape run history."""
    client = get_user_client()
    return (
        client.table("variety_scrape_runs")
        .select("*")
        .order("started_at", desc=True)
        .limit(limit)
        .execute()
        .data
        or []
    )


@st.cache_data(ttl=300)
def get_variety_scrape_logs(run_id: str, limit: int = 100) -> list[dict]:
    """Fetch latest logs for a specific MAFF variety scrape run."""
    client = get_user_client()
    return (
        client.table("variety_scrape_logs")
        .select("*")
        .eq("variety_scrape_run_id", run_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
        .data
        or []
    )

def clear_scrape_cache() -> None:
    """Clear cached scrape run and log queries."""
    get_recent_variety_scrape_runs.clear()
    get_variety_scrape_logs.clear()
