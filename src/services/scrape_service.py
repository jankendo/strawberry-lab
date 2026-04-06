"""Scraped article and GitHub workflow orchestration service."""

from __future__ import annotations

import time
from datetime import datetime, timedelta

import streamlit as st

from src.config import get_config
from src.core.github_client import GitHubClient, WorkflowRunSummary
from src.services.auth_service import get_user_client


@st.cache_data(ttl=300)
def list_articles(
    *,
    source: str | None = None,
    keyword: str | None = None,
    unread_only: bool = False,
    related_variety_id: str | None = None,
    date_from=None,
    date_to=None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int]:
    """List scraped articles with filters."""
    client = get_user_client()
    query = client.table("scraped_articles").select("*")
    if source:
        query = query.eq("source_key", source)
    if unread_only:
        query = query.eq("is_read", False)
    if related_variety_id:
        query = query.eq("related_variety_id", related_variety_id)
    if date_from:
        query = query.gte("scraped_at", f"{date_from}T00:00:00+09:00")
    if date_to:
        query = query.lte("scraped_at", f"{date_to}T23:59:59+09:00")
    if keyword:
        query = query.or_(f"title.ilike.%{keyword}%,summary.ilike.%{keyword}%")
    rows = query.order("scraped_at", desc=True).range((page - 1) * page_size, page * page_size - 1).execute().data or []
    count_query = client.table("scraped_articles").select("id", count="exact", head=True)
    if source:
        count_query = count_query.eq("source_key", source)
    if unread_only:
        count_query = count_query.eq("is_read", False)
    if related_variety_id:
        count_query = count_query.eq("related_variety_id", related_variety_id)
    if date_from:
        count_query = count_query.gte("scraped_at", f"{date_from}T00:00:00+09:00")
    if date_to:
        count_query = count_query.lte("scraped_at", f"{date_to}T23:59:59+09:00")
    if keyword:
        count_query = count_query.or_(f"title.ilike.%{keyword}%,summary.ilike.%{keyword}%")
    total = int(count_query.execute().count or 0)
    return rows, total


def set_article_read_status(article_id: str, is_read: bool) -> None:
    """Toggle article read/unread status."""
    client = get_user_client()
    payload = {"is_read": is_read, "read_at": datetime.utcnow().isoformat() if is_read else None}
    client.table("scraped_articles").update(payload).eq("id", article_id).execute()
    list_articles.clear()


def bulk_mark_filtered_articles_read(filters: dict) -> int:
    """Bulk mark currently filtered articles as read."""
    rows, _ = list_articles(**filters, page=1, page_size=10000)
    if not rows:
        return 0
    client = get_user_client()
    ids = [row["id"] for row in rows if not row.get("is_read")]
    if not ids:
        return 0
    client.table("scraped_articles").update({"is_read": True, "read_at": datetime.utcnow().isoformat()}).in_("id", ids).execute()
    list_articles.clear()
    return len(ids)


@st.cache_data(ttl=300)
def get_recent_scrape_runs(limit: int = 20) -> list[dict]:
    """Fetch recent scraper run history."""
    client = get_user_client()
    return client.table("scrape_runs").select("*").order("started_at", desc=True).limit(limit).execute().data or []


def dispatch_scraper_workflow(source: str) -> None:
    """Dispatch GitHub Actions scrape workflow."""
    gh = GitHubClient(get_config())
    gh.dispatch_scrape(source)


def poll_workflow_status(timeout_seconds: int = 120, interval_seconds: int = 5) -> WorkflowRunSummary | None:
    """Poll latest workflow run status until completion or timeout."""
    gh = GitHubClient(get_config())
    deadline = datetime.utcnow() + timedelta(seconds=timeout_seconds)
    latest: WorkflowRunSummary | None = None
    while datetime.utcnow() < deadline:
        latest = gh.get_latest_run()
        if latest and latest.status == "completed":
            return latest
        time.sleep(interval_seconds)
    return latest
