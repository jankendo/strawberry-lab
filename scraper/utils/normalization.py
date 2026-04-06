"""Normalization utilities for scraped text."""

from __future__ import annotations

import re
import unicodedata


def normalize_article_field(value: str) -> str:
    """Apply NFKC, strip html remnants, and collapse whitespace."""
    text = unicodedata.normalize("NFKC", value or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def normalize_article(article: dict) -> dict:
    """Normalize required article fields."""
    summary = normalize_article_field(article.get("summary", ""))[:3000]
    return {
        **article,
        "article_url": normalize_article_field(article.get("article_url", "")),
        "title": normalize_article_field(article.get("title", "")),
        "summary": summary,
    }
