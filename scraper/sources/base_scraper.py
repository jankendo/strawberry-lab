"""Reusable scraper base class."""

from __future__ import annotations

import os
import time
from abc import ABC
from urllib.parse import urlparse

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
        self._session.headers.update(
            {
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
            }
        )
        self._default_referer = source_config.search_url

    def _wait_rate_limit(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.min_interval_seconds:
            time.sleep(self.min_interval_seconds - elapsed)

    def _build_request_headers(self, url: str, headers: dict[str, str] | None = None) -> dict[str, str]:
        merged = dict(headers or {})
        if "Referer" in merged:
            return merged
        if self._default_referer:
            target = urlparse(url)
            referer = urlparse(self._default_referer)
            if target.scheme == referer.scheme and target.netloc == referer.netloc:
                merged["Referer"] = self._default_referer
        return merged

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict | None = None,
        data: dict | None = None,
        headers: dict[str, str] | None = None,
    ) -> requests.Response:
        if not can_fetch(url, self.user_agent):
            raise PermissionError(f"robots.txt denies scraping: {url}")
        self._wait_rate_limit()
        response = self._session.request(
            method,
            url,
            params=params,
            data=data,
            headers=self._build_request_headers(url, headers),
            timeout=self.timeout_seconds,
        )
        self._last_request_at = time.monotonic()
        response.raise_for_status()
        return response

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8), reraise=True)
    def _get(self, url: str, params: dict | None = None) -> requests.Response:
        return self._request("GET", url, params=params)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8), reraise=True)
    def _post(self, url: str, data: dict | None = None) -> requests.Response:
        return self._request("POST", url, data=data)

    def _soup(self, html: str) -> BeautifulSoup:
        """Parse html to BeautifulSoup tree."""
        return BeautifulSoup(html, "lxml")
