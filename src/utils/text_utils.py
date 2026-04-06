"""Text normalization helpers."""

from __future__ import annotations

import re
import unicodedata


def normalize_text(value: str) -> str:
    """Normalize string with NFKC and collapsed whitespace."""
    normalized = unicodedata.normalize("NFKC", value or "")
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def split_dedup_values(raw_value: str, *, max_items: int, max_length: int) -> list[str]:
    """Split comma-separated values and deduplicate case-insensitively."""
    values: list[str] = []
    seen: set[str] = set()
    for part in raw_value.split(","):
        value = normalize_text(part)
        if not value:
            continue
        key = value.casefold()
        if key in seen:
            continue
        if len(value) > max_length:
            raise ValueError(f"Value too long: {value[:20]}...")
        seen.add(key)
        values.append(value)
    if len(values) > max_items:
        raise ValueError(f"Too many values (max {max_items}).")
    return values
