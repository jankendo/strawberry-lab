"""Reusable scraper base class."""

from __future__ import annotations

import os
import time
from abc import ABC

import requests
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

from scraper.config import SourceConfig
from scraper.utils.robots import can_fetch


class BaseScraper(ABC):
    """Base scraper with robots checks, retries, and rate limiting."""

    def __init__(self, source_config: SourceConfig) -> None:
        self.source_config = source_config
        self.user_agent = os.getenv(
            "SCRAPER_USER_AGENT",
            "StrawberryLabScraper/3.0 (+https://github.com/jankendo/strawberry-lab)",
        )
        self.timeout_seconds = int(os.getenv("SCRAPER_TIMEOUT_SECONDS", "20"))
        self.max_retries = int(os.getenv("SCRAPER_MAX_RETRIES", "3"))
        self.min_interval_seconds = source_config.min_interval_seconds
        self._last_request_at = 0.0
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": self.user_agent})

    def _wait_rate_limit(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.min_interval_seconds:
            time.sleep(self.min_interval_seconds - elapsed)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8), reraise=True)
    def _get(self, url: str, params: dict | None = None) -> requests.Response:
        if not can_fetch(url, self.user_agent):
            raise PermissionError(f"robots.txt denies scraping: {url}")
        self._wait_rate_limit()
        response = self._session.get(url, params=params, timeout=self.timeout_seconds)
        self._last_request_at = time.monotonic()
        response.raise_for_status()
        return response

    def _soup(self, html: str) -> BeautifulSoup:
        """Parse html to BeautifulSoup tree."""
        return BeautifulSoup(html, "lxml")
