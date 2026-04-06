"""Supabase admin client for scraper runtime."""

from __future__ import annotations

from supabase import Client, create_client

from scraper.config import load_config


def get_admin_client() -> Client:
    """Create Supabase client using service role key."""
    cfg = load_config()
    return create_client(cfg.supabase_url, cfg.supabase_service_role_key)
