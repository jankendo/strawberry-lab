"""Client-side asset uploader component wrapper."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import streamlit as st
import streamlit.components.v1 as components

_MIN_COMPONENT_HEIGHT = 260
_MAX_COMPONENT_HEIGHT = 1200
_DEFAULT_MAX_FILES = 5
_DEFAULT_MAX_LONG_EDGE = 2048
_DEFAULT_QUALITY = 0.82
_DEFAULT_REPLAY_EVENT_NAME = "ichigodb:offline-intent-queue-replay-request"
_EVENT_NAME_SANITIZER_RE = re.compile(r"[^A-Za-z0-9._:-]+")
_QUEUE_KEY_SANITIZER_RE = re.compile(r"[^A-Za-z0-9._:-]+")
_MAX_EVENT_NAME_LENGTH = 96
_MAX_QUEUE_KEY_LENGTH = 96
_MAX_DEBUG_MESSAGES = 40
_MAX_DEBUG_MESSAGE_LENGTH = 240
_ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
_ALLOWED_STATUSES = {"idle", "processing", "ready", "uploading", "uploaded", "error"}

_COMPONENT_DIR = Path(__file__).resolve().parent / "asset_uploader_component"

try:
    _ASSET_UPLOADER_COMPONENT = components.declare_component(
        "st_asset_uploader_core",
        path=str(_COMPONENT_DIR),
    )
except Exception:  # pragma: no cover - defensive import fallback
    _ASSET_UPLOADER_COMPONENT = None


def _coerce_int(
    value: object,
    *,
    default: int,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    if isinstance(value, bool):
        numeric = default
    else:
        try:
            numeric = int(round(float(value)))
        except (TypeError, ValueError):
            numeric = default
    if minimum is not None:
        numeric = max(minimum, numeric)
    if maximum is not None:
        numeric = min(maximum, numeric)
    return numeric


def _coerce_float(
    value: object,
    *,
    default: float,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    if isinstance(value, bool):
        numeric = default
    else:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            numeric = default
    if minimum is not None:
        numeric = max(minimum, numeric)
    if maximum is not None:
        numeric = min(maximum, numeric)
    return numeric


def _normalize_status(value: object) -> str:
    text = str(value or "").strip().lower()
    if text in _ALLOWED_STATUSES:
        return text
    return "idle"


def _normalize_event_name(value: object, *, fallback: str = _DEFAULT_REPLAY_EVENT_NAME) -> str:
    text = _EVENT_NAME_SANITIZER_RE.sub("-", str(value or "").strip()).strip("-_.:")
    if not text:
        text = _EVENT_NAME_SANITIZER_RE.sub("-", str(fallback or "").strip()).strip("-_.:")
    if not text:
        text = _DEFAULT_REPLAY_EVENT_NAME
    return text[:_MAX_EVENT_NAME_LENGTH]


def _normalize_queue_key(value: object) -> str:
    text = _QUEUE_KEY_SANITIZER_RE.sub("-", str(value or "").strip()).strip("-_.:")
    if not text:
        return ""
    return text[:_MAX_QUEUE_KEY_LENGTH]


def _normalize_file_entry(raw: Mapping[str, object]) -> dict[str, Any] | None:
    client_file_id = str(raw.get("client_file_id") or "").strip()
    file_name = str(raw.get("file_name") or "").strip()
    mime_type = str(raw.get("mime_type") or "").strip().lower()
    if not client_file_id or not file_name or mime_type not in _ALLOWED_MIME_TYPES:
        return None
    file_size_bytes = _coerce_int(raw.get("file_size_bytes"), default=0, minimum=1)
    width = _coerce_int(raw.get("width"), default=0, minimum=1)
    height = _coerce_int(raw.get("height"), default=0, minimum=1)
    if not file_size_bytes or not width or not height:
        return None
    preview_data_url = str(raw.get("preview_data_url") or "").strip()
    return {
        "client_file_id": client_file_id,
        "file_name": file_name,
        "mime_type": mime_type,
        "file_size_bytes": file_size_bytes,
        "width": width,
        "height": height,
        "preview_data_url": preview_data_url,
    }


def _normalize_debug_messages(raw_debug: object) -> list[str]:
    if not isinstance(raw_debug, Sequence) or isinstance(raw_debug, (str, bytes, bytearray)):
        return []
    debug_messages: list[str] = []
    for item in raw_debug:
        text = str(item or "").strip()
        if text:
            debug_messages.append(text[:_MAX_DEBUG_MESSAGE_LENGTH])
        if len(debug_messages) >= _MAX_DEBUG_MESSAGES:
            break
    return debug_messages


def _normalize_upload_targets(
    raw_targets: Sequence[Mapping[str, object]] | None,
    *,
    max_files: int,
) -> list[dict[str, Any]]:
    if not raw_targets:
        return []
    targets: list[dict[str, Any]] = []
    for raw in raw_targets:
        if not isinstance(raw, Mapping):
            continue
        file_entry = _normalize_file_entry(raw)
        if file_entry is None:
            continue
        signed_upload_url = str(raw.get("signed_upload_url") or "").strip()
        storage_path = str(raw.get("storage_path") or "").strip()
        if not signed_upload_url or not storage_path:
            continue
        targets.append(
            {
                **file_entry,
                "signed_upload_url": signed_upload_url,
                "storage_path": storage_path,
            }
        )
    return targets[:max_files]


def _normalize_component_payload(
    payload: object,
    *,
    max_files: int,
) -> dict[str, Any]:
    data = payload if isinstance(payload, Mapping) else {}
    files_raw = data.get("files")
    uploaded_raw = data.get("uploaded")
    failed_raw = data.get("failed")
    files: list[dict[str, Any]] = []
    uploaded: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    safe_files_raw = files_raw if isinstance(files_raw, Sequence) and not isinstance(files_raw, (str, bytes, bytearray)) else []
    safe_uploaded_raw = (
        uploaded_raw
        if isinstance(uploaded_raw, Sequence) and not isinstance(uploaded_raw, (str, bytes, bytearray))
        else []
    )
    safe_failed_raw = failed_raw if isinstance(failed_raw, Sequence) and not isinstance(failed_raw, (str, bytes, bytearray)) else []
    for raw in safe_files_raw:
        if isinstance(raw, Mapping):
            entry = _normalize_file_entry(raw)
            if entry:
                files.append(entry)
    for raw in safe_uploaded_raw:
        if isinstance(raw, Mapping):
            entry = _normalize_file_entry(raw)
            if not entry:
                continue
            entry["storage_path"] = str(raw.get("storage_path") or "").strip()
            entry["upload_request_token"] = str(raw.get("upload_request_token") or "").strip()
            entry["http_status"] = _coerce_int(raw.get("http_status"), default=200, minimum=100, maximum=599)
            if entry["storage_path"]:
                uploaded.append(entry)
    for raw in safe_failed_raw:
        if isinstance(raw, Mapping):
            entry = _normalize_file_entry(raw)
            if not entry:
                continue
            entry["storage_path"] = str(raw.get("storage_path") or "").strip()
            entry["upload_request_token"] = str(raw.get("upload_request_token") or "").strip()
            entry["error"] = str(raw.get("error") or "アップロードに失敗しました。").strip()
            failed.append(entry)

    debug_messages = _normalize_debug_messages(data.get("debug_messages"))

    return {
        "status": _normalize_status(data.get("status")),
        "files": files[:max_files],
        "uploaded": uploaded[:max_files],
        "failed": failed[:max_files],
        "pending_count": _coerce_int(data.get("pending_count"), default=0, minimum=0),
        "upload_request_token": str(data.get("upload_request_token") or "").strip(),
        "last_processed_upload_token": str(data.get("last_processed_upload_token") or "").strip(),
        "debug_messages": debug_messages,
        "component_available": True,
    }


def _empty_payload(*, debug_messages: Sequence[str] | None = None) -> dict[str, Any]:
    return {
        "status": "idle",
        "files": [],
        "uploaded": [],
        "failed": [],
        "pending_count": 0,
        "upload_request_token": "",
        "last_processed_upload_token": "",
        "debug_messages": _normalize_debug_messages(list(debug_messages or [])),
        "component_available": False,
    }


def render_asset_uploader(
    *,
    key: str,
    max_files: int = _DEFAULT_MAX_FILES,
    label: str = "画像アップロード",
    disabled: bool = False,
    height: int = 420,
    max_long_edge: int = _DEFAULT_MAX_LONG_EDGE,
    quality: float = _DEFAULT_QUALITY,
    upload_targets: Sequence[Mapping[str, object]] | None = None,
    upload_request_token: str | None = None,
    clear_token: str | None = None,
    replay_event_name: str = _DEFAULT_REPLAY_EVENT_NAME,
    replay_queue_key: str | None = None,
    debug: bool = False,
) -> dict[str, Any]:
    """Render client-side image uploader and return normalized component state."""
    safe_key = str(key or "asset-uploader")
    safe_max_files = _coerce_int(max_files, default=_DEFAULT_MAX_FILES, minimum=1, maximum=10)
    safe_height = _coerce_int(height, default=420, minimum=_MIN_COMPONENT_HEIGHT, maximum=_MAX_COMPONENT_HEIGHT)
    safe_max_long_edge = _coerce_int(
        max_long_edge,
        default=_DEFAULT_MAX_LONG_EDGE,
        minimum=320,
        maximum=4096,
    )
    safe_quality = _coerce_float(quality, default=_DEFAULT_QUALITY, minimum=0.3, maximum=0.98)
    safe_upload_targets = _normalize_upload_targets(upload_targets, max_files=safe_max_files)
    safe_upload_request_token = str(upload_request_token or "").strip()
    safe_clear_token = str(clear_token or "").strip()
    safe_replay_event_name = _normalize_event_name(replay_event_name, fallback=_DEFAULT_REPLAY_EVENT_NAME)
    safe_replay_queue_key = _normalize_queue_key(replay_queue_key)

    if _ASSET_UPLOADER_COMPONENT is None:
        st.caption("画像アップローダーを読み込めなかったため、画像最適化機能を利用できません。")
        return _empty_payload(debug_messages=["component_unavailable:asset_uploader_component_missing"])

    default_payload = {
        "status": "idle",
        "files": [],
        "uploaded": [],
        "failed": [],
        "pending_count": 0,
        "upload_request_token": "",
        "last_processed_upload_token": "",
    }
    try:
        payload = _ASSET_UPLOADER_COMPONENT(
            key=safe_key,
            default=default_payload,
            componentKey=safe_key,
            label=str(label or "画像アップロード"),
            maxFiles=safe_max_files,
            disabled=bool(disabled),
            height=safe_height,
            maxLongEdge=safe_max_long_edge,
            quality=safe_quality,
            uploadTargets=safe_upload_targets,
            uploadRequestToken=safe_upload_request_token,
            clearToken=safe_clear_token,
            replayEventName=safe_replay_event_name,
            replayQueueKey=safe_replay_queue_key,
            debug=bool(debug),
        )
    except Exception as exc:
        st.caption("画像アップローダーの初期化に失敗したため、標準アップロードへフォールバックします。")
        error_text = str(exc).strip() or "unknown"
        return _empty_payload(debug_messages=[f"component_init_error:{type(exc).__name__}:{error_text}"])
    return _normalize_component_payload(payload, max_files=safe_max_files)
