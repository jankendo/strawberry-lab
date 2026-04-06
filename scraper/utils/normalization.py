"""Normalization utilities for scraper text payloads."""

from __future__ import annotations

import re
import unicodedata


def normalize_text(value: str) -> str:
    """Apply NFKC, strip html remnants, and collapse whitespace."""
    text = unicodedata.normalize("NFKC", value or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def normalize_article_field(value: str) -> str:
    """Backward-compatible alias of normalize_text."""
    return normalize_text(value)


def normalize_article(article: dict) -> dict:
    """Backward-compatible article-normalization helper."""
    summary = normalize_text(article.get("summary", ""))[:3000]
    return {
        **article,
        "article_url": normalize_text(article.get("article_url", "")),
        "title": normalize_text(article.get("title", "")),
        "summary": summary,
    }
