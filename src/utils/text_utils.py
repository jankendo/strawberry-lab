"""Text normalization helpers."""

from __future__ import annotations

from collections.abc import Iterable
import re
import unicodedata

_HIRAGANA_START = ord("ぁ")
_HIRAGANA_END = ord("ゖ")
_KANA_OFFSET = ord("ァ") - ord("ぁ")
_HIRAGANA_EXTRA_MAP = str.maketrans({"ゝ": "ヽ", "ゞ": "ヾ"})


def normalize_text(value: str) -> str:
    """Normalize string with NFKC and collapsed whitespace."""
    normalized = unicodedata.normalize("NFKC", value or "")
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def fold_hiragana_to_katakana(value: str) -> str:
    """Fold hiragana into katakana for kana-insensitive matching."""
    folded_chars: list[str] = []
    for char in normalize_text(value).translate(_HIRAGANA_EXTRA_MAP):
        code_point = ord(char)
        if _HIRAGANA_START <= code_point <= _HIRAGANA_END:
            folded_chars.append(chr(code_point + _KANA_OFFSET))
        else:
            folded_chars.append(char)
    return "".join(folded_chars)


def normalize_search_text(value: str) -> str:
    """Normalize search text so hiragana and katakana match each other."""
    normalized = fold_hiragana_to_katakana(value).casefold()
    normalized = re.sub(r"\s+", "", normalized)
    return normalized.strip()


def build_search_key(values: Iterable[object | None]) -> str:
    """Build a compact search key from strings and string lists."""
    parts: list[str] = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, (list, tuple, set)):
            parts.extend(
                normalized
                for normalized in (normalize_search_text(str(item)) for item in value if item not in {None, ""})
                if normalized
            )
            continue
        normalized = normalize_search_text(str(value))
        if normalized:
            parts.append(normalized)
    return " ".join(parts)


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
