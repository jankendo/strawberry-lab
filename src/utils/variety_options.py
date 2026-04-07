"""Shared helpers for kana-insensitive variety option filtering."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from src.utils.text_utils import build_search_key, normalize_search_text


def build_variety_option_search_key(variety: Mapping[str, object]) -> str:
    """Build a kana-insensitive search key for variety option pickers."""
    prebuilt = variety.get("_search_key")
    if isinstance(prebuilt, str) and prebuilt.strip():
        return prebuilt
    return build_search_key(
        [
            variety.get("name"),
            variety.get("alias_names") or [],
            variety.get("japanese_name"),
            variety.get("registration_number"),
            variety.get("application_number"),
        ]
    )


def filter_variety_selection_options(
    varieties: Sequence[Mapping[str, object]],
    keyword: str,
    *,
    include_ids: Sequence[str] = (),
) -> list[dict]:
    """Filter variety options with hiragana/katakana-insensitive matching."""
    normalized_keyword = normalize_search_text(keyword or "")
    forced_ids = {str(value) for value in include_ids if str(value).strip()}
    filtered: list[dict] = []
    seen_ids: set[str] = set()
    for variety in varieties:
        variety_id = str(variety.get("id") or "").strip()
        if not variety_id or variety_id in seen_ids:
            continue
        search_key = build_variety_option_search_key(variety)
        if variety_id in forced_ids or not normalized_keyword or normalized_keyword in search_key:
            filtered.append(dict(variety))
            seen_ids.add(variety_id)
    return filtered
