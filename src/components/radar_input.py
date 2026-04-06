"""Bidirectional wrapper for a five-axis draggable radar input component."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import streamlit as st
import streamlit.components.v1 as components

_DEFAULT_AXIS_KEYS = ("sweetness", "sourness", "aroma", "texture", "appearance")
_DEFAULT_AXIS_LABELS = {
    "sweetness": "甘味",
    "sourness": "酸味",
    "aroma": "香り",
    "texture": "食感",
    "appearance": "見た目",
}
_MIN_COMPONENT_HEIGHT = 260
_MAX_COMPONENT_HEIGHT = 920

_COMPONENT_DIR = Path(__file__).resolve().parent / "radar_input_component"

try:
    _RADAR_INPUT_COMPONENT = components.declare_component(
        "st_radar_input_core",
        path=str(_COMPONENT_DIR),
    )
except Exception:  # pragma: no cover - defensive import fallback
    _RADAR_INPUT_COMPONENT = None


def _coerce_int(value: object, *, default: int) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return default


def _normalize_axis_keys(axis_keys: Sequence[object] | None) -> tuple[str, ...]:
    if axis_keys is None:
        return _DEFAULT_AXIS_KEYS

    normalized: list[str] = []
    seen: set[str] = set()
    for raw_key in axis_keys:
        key = str(raw_key or "").strip()
        if not key or key in seen:
            continue
        normalized.append(key)
        seen.add(key)
        if len(normalized) == len(_DEFAULT_AXIS_KEYS):
            break

    if len(normalized) != len(_DEFAULT_AXIS_KEYS):
        return _DEFAULT_AXIS_KEYS
    return tuple(normalized)


def _snap_score(value: int, *, min_value: int, max_value: int, step: int) -> int:
    clamped = max(min_value, min(max_value, value))
    if step <= 1:
        return clamped
    offset = clamped - min_value
    snapped = min_value + int(round(offset / step)) * step
    return max(min_value, min(max_value, snapped))


def _normalize_scale(
    *,
    min_value: object,
    max_value: object,
    step: object,
    default_value: object,
) -> tuple[int, int, int, int]:
    normalized_min = _coerce_int(min_value, default=1)
    normalized_max = _coerce_int(max_value, default=5)

    if normalized_min > normalized_max:
        normalized_min, normalized_max = normalized_max, normalized_min
    if normalized_min == normalized_max:
        normalized_max = normalized_min + 1

    normalized_step = max(1, _coerce_int(step, default=1))
    normalized_step = min(normalized_step, max(1, normalized_max - normalized_min))

    midpoint_default = normalized_min + (normalized_max - normalized_min) // 2
    normalized_default = _coerce_int(default_value, default=midpoint_default)
    normalized_default = _snap_score(
        normalized_default,
        min_value=normalized_min,
        max_value=normalized_max,
        step=normalized_step,
    )
    return normalized_min, normalized_max, normalized_step, normalized_default


def _normalize_axis_labels(
    axis_keys: Sequence[str],
    axis_labels: Mapping[str, object] | None,
) -> dict[str, str]:
    safe_labels: dict[str, str] = {}
    for axis_key in axis_keys:
        fallback_label = _DEFAULT_AXIS_LABELS.get(axis_key, axis_key)
        if axis_labels and axis_key in axis_labels:
            label = str(axis_labels[axis_key] or "").strip() or fallback_label
        else:
            label = fallback_label
        safe_labels[axis_key] = label
    return safe_labels


def _normalize_scores(
    value: Mapping[str, object] | None,
    *,
    axis_keys: Sequence[str],
    min_value: int,
    max_value: int,
    step: int,
    default_value: int,
) -> dict[str, int]:
    normalized: dict[str, int] = {}
    source = value if isinstance(value, Mapping) else {}
    for axis_key in axis_keys:
        raw_score = source.get(axis_key, default_value)
        score = _coerce_int(raw_score, default=default_value)
        normalized[axis_key] = _snap_score(
            score,
            min_value=min_value,
            max_value=max_value,
            step=step,
        )
    return normalized


def _extract_component_payload(payload: object) -> Mapping[str, object] | None:
    if not isinstance(payload, Mapping):
        return None
    nested = payload.get("scores")
    if isinstance(nested, Mapping):
        return nested
    return payload


def _normalize_component_scores(
    payload: object,
    *,
    axis_keys: Sequence[str],
    min_value: int,
    max_value: int,
    step: int,
    default_value: int,
) -> dict[str, int] | None:
    raw_scores = _extract_component_payload(payload)
    if raw_scores is None:
        return None
    return _normalize_scores(
        raw_scores,
        axis_keys=axis_keys,
        min_value=min_value,
        max_value=max_value,
        step=step,
        default_value=default_value,
    )


def _render_slider_fallback(
    *,
    key: str,
    axis_keys: Sequence[str],
    axis_labels: Mapping[str, str],
    scores: Mapping[str, int],
    min_value: int,
    max_value: int,
    step: int,
    disabled: bool,
) -> dict[str, int]:
    st.caption("レーダー入力を読み込めなかったため、スライダー入力に切り替えました。")
    columns = st.columns(len(axis_keys))
    fallback_scores: dict[str, int] = {}
    for index, axis_key in enumerate(axis_keys):
        with columns[index]:
            fallback_scores[axis_key] = int(
                st.slider(
                    axis_labels[axis_key],
                    min_value=min_value,
                    max_value=max_value,
                    value=int(scores[axis_key]),
                    step=step,
                    key=f"{key}-radar-fallback-{axis_key}",
                    disabled=disabled,
                )
            )
    return fallback_scores


def render_radar_input(
    *,
    key: str,
    value: Mapping[str, object] | None = None,
    axis_keys: Sequence[object] | None = None,
    axis_labels: Mapping[str, object] | None = None,
    min_value: int = 1,
    max_value: int = 5,
    default_value: int = 3,
    step: int = 1,
    height: int = 360,
    disabled: bool = False,
    use_native_fallback: bool = True,
) -> dict[str, int]:
    """Render the draggable radar input and return normalized axis scores."""

    safe_axis_keys = _normalize_axis_keys(axis_keys)
    safe_min, safe_max, safe_step, safe_default = _normalize_scale(
        min_value=min_value,
        max_value=max_value,
        step=step,
        default_value=default_value,
    )
    safe_labels = _normalize_axis_labels(safe_axis_keys, axis_labels)
    safe_input_scores = _normalize_scores(
        value,
        axis_keys=safe_axis_keys,
        min_value=safe_min,
        max_value=safe_max,
        step=safe_step,
        default_value=safe_default,
    )
    safe_height = max(
        _MIN_COMPONENT_HEIGHT,
        min(_MAX_COMPONENT_HEIGHT, _coerce_int(height, default=360)),
    )
    safe_key = str(key or "radar-input")

    if _RADAR_INPUT_COMPONENT is None:
        if use_native_fallback:
            return _render_slider_fallback(
                key=safe_key,
                axis_keys=safe_axis_keys,
                axis_labels=safe_labels,
                scores=safe_input_scores,
                min_value=safe_min,
                max_value=safe_max,
                step=safe_step,
                disabled=bool(disabled),
            )
        return safe_input_scores

    axes_payload = [{"key": axis_key, "label": safe_labels[axis_key]} for axis_key in safe_axis_keys]
    component_default: dict[str, Any] = {"scores": safe_input_scores}

    try:
        payload = _RADAR_INPUT_COMPONENT(
            key=safe_key,
            default=component_default,
            axes=axes_payload,
            scores=safe_input_scores,
            minValue=safe_min,
            maxValue=safe_max,
            step=safe_step,
            height=safe_height,
            disabled=bool(disabled),
        )
    except Exception:
        payload = None

    normalized_output = _normalize_component_scores(
        payload,
        axis_keys=safe_axis_keys,
        min_value=safe_min,
        max_value=safe_max,
        step=safe_step,
        default_value=safe_default,
    )
    if normalized_output is not None:
        return normalized_output
    if use_native_fallback:
        return _render_slider_fallback(
            key=safe_key,
            axis_keys=safe_axis_keys,
            axis_labels=safe_labels,
            scores=safe_input_scores,
            min_value=safe_min,
            max_value=safe_max,
            step=safe_step,
            disabled=bool(disabled),
        )
    return safe_input_scores
