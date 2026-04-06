"""Scraper runtime configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class SourceConfig:
    """Per-source scraping settings."""

    source_key: str
    source_name: str
    enabled: bool
    search_url: str
    min_interval_seconds: int
    max_pages_per_run: int


@dataclass(frozen=True)
class ScraperConfig:
    """Top-level scraper config."""

    supabase_url: str
    supabase_service_role_key: str
    app_timezone: str
    user_agent: str
    timeout_seconds: int
    max_retries: int
    sources: dict[str, SourceConfig]


def load_config() -> ScraperConfig:
    """Load scraper config from environment."""
    return ScraperConfig(
        supabase_url=os.environ["SUPABASE_URL"],
        supabase_service_role_key=os.environ["SUPABASE_SERVICE_ROLE_KEY"],
        app_timezone=os.getenv("APP_TIMEZONE", "Asia/Tokyo"),
        user_agent="StrawberryLabScraper/3.0 (+https://github.com/jankendo/strawberry-lab)",
        timeout_seconds=20,
        max_retries=3,
        sources={
            "maff": SourceConfig(
                source_key="maff",
                source_name="MAFF Variety Registry",
                enabled=True,
                search_url="https://www.hinshu2.maff.go.jp/vips/cmm/apCMM110.aspx?MOSS=1",
                min_interval_seconds=5,
                max_pages_per_run=200,
            )
        },
    )
