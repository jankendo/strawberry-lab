"""Hashing helpers for scraped article deduplication."""

from __future__ import annotations

import hashlib

from scraper.utils.normalization import normalize_article_field


def compute_article_hash(article_url: str, title: str, summary: str) -> str:
    """Compute SHA-256 from normalized article fields."""
    normalized = "\n".join(
        [
            normalize_article_field(article_url),
            normalize_article_field(title),
            normalize_article_field(summary),
        ]
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
