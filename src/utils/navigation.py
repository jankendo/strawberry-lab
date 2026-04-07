"""Navigation helpers for query-param based page handoff."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

REVIEW_VARIETY_QUERY_PARAM = "review_variety_id"
SELECTED_VARIETY_QUERY_PARAM = "selected_variety_id"


def _normalize_query_value(value: object) -> str:
    text = str(value or "").strip()
    return text


def _first_query_value(value: object) -> str:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            text = _normalize_query_value(item)
            if text:
                return text
        return ""
    return _normalize_query_value(value)


def build_single_query_param(key: str, value: object) -> dict[str, str]:
    query_key = _normalize_query_value(key)
    query_value = _normalize_query_value(value)
    if not query_key or not query_value:
        return {}
    return {query_key: query_value}


def resolve_single_query_param(query_params: Mapping[str, object] | None, key: str) -> str:
    if not isinstance(query_params, Mapping):
        return ""
    query_key = _normalize_query_value(key)
    if not query_key:
        return ""
    return _first_query_value(query_params.get(query_key))


def build_review_variety_query_params(variety_id: object) -> dict[str, str]:
    return build_single_query_param(REVIEW_VARIETY_QUERY_PARAM, variety_id)


def build_selected_variety_query_params(variety_id: object) -> dict[str, str]:
    return build_single_query_param(SELECTED_VARIETY_QUERY_PARAM, variety_id)


def resolve_review_variety_query_param(query_params: Mapping[str, object] | None) -> str:
    return resolve_single_query_param(query_params, REVIEW_VARIETY_QUERY_PARAM)


def resolve_selected_variety_query_param(query_params: Mapping[str, object] | None) -> str:
    return resolve_single_query_param(query_params, SELECTED_VARIETY_QUERY_PARAM)
