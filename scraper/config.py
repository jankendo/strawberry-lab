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
    listing_urls: list[str]
    min_interval_seconds: int
    max_articles_per_run: int


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
        user_agent="StrawberryLabScraper/2.0 (+https://github.com/)",
        timeout_seconds=20,
        max_retries=3,
        sources={
            "maff": SourceConfig("maff", "MAFF", True, ["https://www.maff.go.jp/j/seisan/"], 5, 30),
            "naro": SourceConfig("naro", "NARO", True, ["https://www.naro.go.jp/publicity_report/"], 5, 30),
            "ja_news": SourceConfig("ja_news", "JA News", True, ["https://www.agrinews.co.jp/"], 5, 30),
        },
    )
