"""Hashing helpers for scraper deduplication."""

from __future__ import annotations

import hashlib

from scraper.utils.normalization import normalize_text


def compute_article_hash(article_url: str, title: str, summary: str) -> str:
    """Compute SHA-256 from normalized text fields."""
    normalized = "\n".join(
        [
            normalize_text(article_url),
            normalize_text(title),
            normalize_text(summary),
        ]
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def compute_variety_hash(registration_number: str, name: str, detail_url: str) -> str:
    """Compute SHA-256 fingerprint for MAFF variety rows."""
    normalized = "\n".join(
        [
            normalize_text(registration_number),
            normalize_text(name),
            normalize_text(detail_url),
        ]
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
