"""Supabase heartbeat job."""

from __future__ import annotations

from scraper.utils.supabase_admin import get_admin_client


def run_heartbeat() -> int:
    """Ping Supabase with a minimal query."""
    client = get_admin_client()
    client.table("scrape_runs").select("id").limit(1).execute()
    return 0


if __name__ == "__main__":
    raise SystemExit(run_heartbeat())
