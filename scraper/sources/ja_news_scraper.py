"""JA News source scraper."""

from __future__ import annotations

from bs4 import BeautifulSoup

from scraper.sources.base_scraper import BaseScraper


class JaNewsScraper(BaseScraper):
    """Scraper for JA News pages."""

    def fetch_article_links(self) -> list[str]:
        links: list[str] = []
        for listing_url in self.source_config.listing_urls:
            response = self._get(listing_url)
            links.extend(self.parse_links_from_html(response.text, "https://www.agrinews.co.jp"))
        return [link for link in links if "agrinews.co.jp" in link][: self.source_config.max_articles_per_run]

    def fetch_article(self, article_url: str) -> dict:
        response = self._get(article_url)
        soup = BeautifulSoup(response.text, "lxml")
        title = (soup.title.string or "").strip() if soup.title else article_url
        summary = " ".join(p.get_text(" ", strip=True) for p in soup.select("p")[:8])[:3000]
        return {
            "source_key": self.source_config.source_key,
            "source_name": self.source_config.source_name,
            "listing_url": self.source_config.listing_urls[0],
            "article_url": article_url,
            "title": title,
            "summary": summary,
            "published_at": None,
            "raw_metadata": {},
        }
