"""Reusable scraper base class."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod

import requests
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

from scraper.config import SourceConfig, load_config
from scraper.utils.robots import can_fetch


class BaseScraper(ABC):
    """Base scraper with robots checks, retries, and rate limiting."""

    def __init__(self, source_config: SourceConfig) -> None:
        self.source_config = source_config
        cfg = load_config()
        self.user_agent = cfg.user_agent
        self.timeout_seconds = cfg.timeout_seconds
        self.min_interval_seconds = source_config.min_interval_seconds
        self._last_request_at = 0.0

    def _wait_rate_limit(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.min_interval_seconds:
            time.sleep(self.min_interval_seconds - elapsed)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8), reraise=True)
    def _get(self, url: str) -> requests.Response:
        if not can_fetch(url, self.user_agent):
            raise PermissionError(f"robots.txt denies scraping: {url}")
        self._wait_rate_limit()
        response = requests.get(url, headers={"User-Agent": self.user_agent}, timeout=self.timeout_seconds)
        self._last_request_at = time.monotonic()
        response.raise_for_status()
        return response

    @abstractmethod
    def fetch_article_links(self) -> list[str]:
        """Fetch article links from listing pages."""

    @abstractmethod
    def fetch_article(self, article_url: str) -> dict:
        """Fetch and parse one article."""

    def run(self) -> list[dict]:
        """Run source scraper and return normalized article candidates."""
        links = self.fetch_article_links()[: self.source_config.max_articles_per_run]
        results: list[dict] = []
        for url in links:
            try:
                results.append(self.fetch_article(url))
            except Exception:
                continue
        return results

    def parse_links_from_html(self, html: str, base_url: str) -> list[str]:
        """Extract article-like links from HTML."""
        soup = BeautifulSoup(html, "lxml")
        links: list[str] = []
        for a in soup.select("a[href]"):
            href = a.get("href", "").strip()
            if not href:
                continue
            if href.startswith("/"):
                href = f"{base_url.rstrip('/')}{href}"
            if href.startswith("http"):
                links.append(href)
        dedup: list[str] = []
        seen: set[str] = set()
        for link in links:
            if link in seen:
                continue
            seen.add(link)
            dedup.append(link)
        return dedup
