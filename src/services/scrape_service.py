"""GitHub workflow orchestration for MAFF variety scraping."""

from __future__ import annotations

import time
from datetime import datetime, timedelta

import streamlit as st

from src.config import get_config
from src.core.github_client import GitHubClient, WorkflowRunSummary
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


def dispatch_scraper_workflow() -> None:
    """Dispatch GitHub Actions workflow for MAFF variety scraping."""
    gh = GitHubClient(get_config())
    gh.dispatch_scrape()
    get_recent_variety_scrape_runs.clear()
    get_variety_scrape_logs.clear()


def poll_workflow_status(timeout_seconds: int = 120, interval_seconds: int = 5) -> WorkflowRunSummary | None:
    """Poll latest workflow run status until completion or timeout."""
    gh = GitHubClient(get_config())
    deadline = datetime.utcnow() + timedelta(seconds=timeout_seconds)
    latest: WorkflowRunSummary | None = None
    while datetime.utcnow() < deadline:
        latest = gh.get_latest_run()
        if latest and latest.status == "completed":
            get_recent_variety_scrape_runs.clear()
            get_variety_scrape_logs.clear()
            return latest
        time.sleep(interval_seconds)
    return latest
