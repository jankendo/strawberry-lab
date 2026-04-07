"""Reviews page."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime
from uuid import uuid4

import streamlit as st

from src.components.asset_uploader import render_asset_uploader
from src.components.draft_buffer import clear_draft_buffer, render_draft_buffer_bridge
from src.components.offline_queue import (
    enqueue_offline_intent,
    remove_offline_intent,
    render_offline_intent_queue_bridge,
    trigger_offline_intent_replay,
)
from src.components.layout import (
    inject_app_style,
    render_action_bar,
    render_empty_state,
    render_hero_banner,
    render_kpi_cards,
    render_section_title,
    render_status_badge,
    render_sticky_primary_action_anchor,
    render_surface,
)
from src.components.pagination import render_pagination_controls
from src.components.radar_input import render_radar_input
from src.components.sidebar import render_primary_nav, render_sidebar
from src.components.tables import is_mobile_client, render_table
from src.constants.ui import EMPTY_STATE_MESSAGE
from src.services.auth_service import require_admin_session
from src.services.review_service import create_or_update_review, list_reviews, restore_review, soft_delete_review
from src.services.storage_service import (
    finalize_review_image_direct_uploads,
    prepare_review_image_direct_upload_targets,
    upload_review_image,
)
from src.services.variety_service import list_active_varieties
from src.utils.navigation import resolve_review_variety_query_param
from src.utils.validation import normalize_review_tasted_date

_PENDING_DUPLICATE_PAYLOAD_KEY = "reviews_pending_duplicate_payload"
_PENDING_DUPLICATE_FILES_KEY = "reviews_pending_duplicate_files"
_SCORE_GUIDE_TEXT = "1=弱い / 3=普通 / 5=強い"
_REVIEW_SCORE_BASELINE_KEY = "review_score_baseline"
_REVIEW_SCORE_AXIS_KEYS = ("sweetness", "sourness", "aroma", "texture", "appearance")
_REVIEW_SCORE_FIELD_KEYS = {axis_key: f"review_{axis_key}" for axis_key in _REVIEW_SCORE_AXIS_KEYS}
_REVIEW_SCORE_RADAR_LABELS = {
    "sweetness": "甘味",
    "sourness": "酸味",
    "aroma": "香り",
    "texture": "食感",
    "appearance": "見た目",
}
_REVIEW_DRAFT_KEY = "reviews-entry-form"
_REVIEW_DRAFT_CLEAR_KEY = "reviews_clear_draft_on_render"
_REVIEW_DRAFT_DISCARD_NOTICE_KEY = "reviews_draft_discard_notice"
_REVIEWS_PENDING_SAVE_INTENT_KEY = "reviews_pending_save_intent"
_REVIEWS_PENDING_SAVE_INTENT_REMOVALS_KEY = "reviews_pending_save_intent_removals"
_REVIEWS_SAVE_INTENT_QUEUE_KEY = "reviews-save-intent-queue"
_REVIEWS_SAVE_INTENT_REPLAY_EVENT = "ichigodb:reviews-save-intent-replay-request"
_REVIEWS_IMAGE_UPLOAD_QUEUE_KEY = "reviews-image-upload-queue"
_REVIEWS_IMAGE_UPLOAD_REPLAY_EVENT = "ichigodb:reviews-image-upload-replay-request"
_REVIEW_ASSET_UPLOADER_KEY = "review_asset_uploader"
_REVIEWS_PENDING_IMAGE_UPLOAD_KEY = "reviews_pending_image_upload"
_REVIEWS_PENDING_IMAGE_UPLOAD_INTENT_REMOVALS_KEY = "reviews_pending_image_upload_intent_removals"
_REVIEWS_ASSET_CLEAR_TOKEN_KEY = "reviews_asset_clear_token"
_REVIEW_DRAFT_FIELDS = [
    {"name": "variety_id", "label": "品種 *", "kind": "select"},
    {"name": "tasted_date", "label": "試食日 *", "kind": "date"},
    {"name": "sweetness", "label": "甘味 *", "kind": "slider"},
    {"name": "sourness", "label": "酸味 *", "kind": "slider"},
    {"name": "aroma", "label": "香り *", "kind": "slider"},
    {"name": "texture", "label": "食感 *", "kind": "slider"},
    {"name": "appearance", "label": "見た目 *", "kind": "slider"},
    {"name": "purchase_place", "label": "購入場所", "kind": "text"},
    {"name": "price_jpy", "label": "価格（円）", "kind": "number"},
    {"name": "comment", "label": "コメント", "kind": "textarea"},
]
_SCORE_LEVEL_LABELS = {
    1: "弱い",
    2: "やや弱い",
    3: "普通",
    4: "やや強い",
    5: "強い",
}
_REVIEWS_RETRIABLE_SAVE_ERROR_HINTS = (
    "connection",
    "connect",
    "network",
    "offline",
    "timeout",
    "timed out",
    "transport",
    "temporarily unavailable",
    "service unavailable",
    "gateway timeout",
    "bad gateway",
    "failed to fetch",
    "disconnected",
    "name or service not known",
    "dns",
    "connection reset",
    "connection aborted",
)
_REVIEWS_RETRIABLE_SAVE_ERROR_TYPES = ("timeout", "connection", "network", "transport")


def _variety_name_map(varieties: list[dict]) -> dict[str, str]:
    return {str(variety["id"]): str(variety.get("name") or variety["id"]) for variety in varieties}


def _collect_upload_files(uploaded_files) -> list[tuple[str, bytes]]:
    return [(uploaded.name, uploaded.getvalue()) for uploaded in (uploaded_files or [])[:3]]


def _collect_component_upload_files(component_state: Mapping[str, object] | None) -> list[dict]:
    if not isinstance(component_state, Mapping):
        return []
    files = component_state.get("files")
    if not isinstance(files, list):
        return []
    normalized: list[dict] = []
    for entry in files[:3]:
        if isinstance(entry, Mapping):
            normalized.append(dict(entry))
    return normalized


def _upload_review_images(review_id: str, files_to_upload: list[tuple[str, bytes]]) -> None:
    for file_name, raw_bytes in files_to_upload:
        upload_review_image(review_id, file_name, raw_bytes)


def _clear_pending_duplicate() -> None:
    st.session_state.pop(_PENDING_DUPLICATE_PAYLOAD_KEY, None)
    st.session_state.pop(_PENDING_DUPLICATE_FILES_KEY, None)


def _set_pending_duplicate_files(
    *,
    component_files: Sequence[Mapping[str, object]] | None = None,
    fallback_files: Sequence[tuple[str, bytes]] | None = None,
) -> None:
    normalized_component_files: list[dict] = []
    for entry in (component_files or [])[:3]:
        if isinstance(entry, Mapping):
            normalized_component_files.append(dict(entry))
    normalized_fallback_files: list[tuple[str, bytes]] = []
    for entry in (fallback_files or [])[:3]:
        if not isinstance(entry, tuple) or len(entry) != 2:
            continue
        file_name, raw_bytes = entry
        if not isinstance(file_name, str) or not isinstance(raw_bytes, (bytes, bytearray)):
            continue
        normalized_fallback_files.append((file_name, bytes(raw_bytes)))
    st.session_state[_PENDING_DUPLICATE_FILES_KEY] = {
        "component_files": normalized_component_files,
        "fallback_files": normalized_fallback_files,
    }


def _resolve_pending_duplicate_files() -> tuple[list[dict], list[tuple[str, bytes]]]:
    pending_files = st.session_state.get(_PENDING_DUPLICATE_FILES_KEY)
    component_files: list[dict] = []
    fallback_files: list[tuple[str, bytes]] = []
    if isinstance(pending_files, Mapping):
        raw_component_files = pending_files.get("component_files")
        raw_fallback_files = pending_files.get("fallback_files")
        if isinstance(raw_component_files, list):
            for entry in raw_component_files[:3]:
                if isinstance(entry, Mapping):
                    component_files.append(dict(entry))
        if isinstance(raw_fallback_files, list):
            for entry in raw_fallback_files[:3]:
                if isinstance(entry, tuple) and len(entry) == 2:
                    file_name, raw_bytes = entry
                    if isinstance(file_name, str) and isinstance(raw_bytes, (bytes, bytearray)):
                        fallback_files.append((file_name, bytes(raw_bytes)))
        return component_files, fallback_files
    if isinstance(pending_files, list):
        for entry in pending_files[:3]:
            if isinstance(entry, Mapping):
                component_files.append(dict(entry))
            elif isinstance(entry, tuple) and len(entry) == 2:
                file_name, raw_bytes = entry
                if isinstance(file_name, str) and isinstance(raw_bytes, (bytes, bytearray)):
                    fallback_files.append((file_name, bytes(raw_bytes)))
    return component_files, fallback_files


def _resolve_pending_image_upload() -> dict | None:
    pending = st.session_state.get(_REVIEWS_PENDING_IMAGE_UPLOAD_KEY)
    if not isinstance(pending, dict):
        return None
    intent_id = str(pending.get("intent_id") or "").strip()
    token = str(pending.get("token") or "").strip()
    review_id = str(pending.get("review_id") or "").strip()
    targets = pending.get("targets")
    if not token or not review_id or not isinstance(targets, list):
        if intent_id:
            _queue_pending_image_upload_intent_removal(intent_id)
        st.session_state.pop(_REVIEWS_PENDING_IMAGE_UPLOAD_KEY, None)
        return None
    expected_count = int(pending.get("expected_count") or len(targets))
    return {
        "intent_id": intent_id,
        "token": token,
        "review_id": review_id,
        "targets": [dict(target) for target in targets if isinstance(target, Mapping)],
        "expected_count": max(0, expected_count),
        "success_message": str(pending.get("success_message") or "保存しました。"),
    }


def _set_pending_image_upload(*, review_id: str, targets: list[dict], success_message: str) -> None:
    if not targets:
        _clear_pending_image_upload()
        return
    normalized_targets = [dict(target) for target in targets if isinstance(target, Mapping)]
    if not normalized_targets:
        _clear_pending_image_upload()
        return
    existing_pending = _resolve_pending_image_upload()
    existing_intent_id = existing_pending["intent_id"] if existing_pending else None
    upload_token = str(uuid4())
    queue_payload = {
        "token": upload_token,
        "review_id": str(review_id),
        "expected_count": len(normalized_targets),
    }
    intent_id = enqueue_offline_intent(
        _REVIEWS_IMAGE_UPLOAD_QUEUE_KEY,
        intent_id=existing_intent_id,
        intent_type="reviews:image-upload",
        payload=queue_payload,
        metadata={"page": "02_reviews"},
    )
    st.session_state[_REVIEWS_PENDING_IMAGE_UPLOAD_KEY] = {
        "intent_id": intent_id,
        "token": upload_token,
        "review_id": str(review_id),
        "targets": normalized_targets,
        "expected_count": len(normalized_targets),
        "success_message": str(success_message or "保存しました。"),
    }


def _clear_pending_image_upload() -> None:
    pending = _resolve_pending_image_upload()
    st.session_state.pop(_REVIEWS_PENDING_IMAGE_UPLOAD_KEY, None)
    intent_id = str((pending or {}).get("intent_id") or "").strip()
    if intent_id:
        _queue_pending_image_upload_intent_removal(intent_id)


def _normalize_pending_payload(payload: dict) -> dict:
    normalized_payload = payload.copy()
    normalized_payload["tasted_date"] = normalize_review_tasted_date(normalized_payload["tasted_date"])
    return normalized_payload


def _score_level_label(value: int) -> str:
    return _SCORE_LEVEL_LABELS.get(int(value), "普通")


def _normalize_score_value(value: object, *, fallback: int = 3) -> int:
    try:
        numeric = int(round(float(value)))
    except (TypeError, ValueError):
        numeric = fallback
    return max(1, min(5, numeric))


def _coerce_score_map(raw_scores: Mapping[str, object] | None, *, fallback: dict[str, int]) -> dict[str, int]:
    source = raw_scores if isinstance(raw_scores, Mapping) else {}
    return {
        axis_key: _normalize_score_value(source.get(axis_key), fallback=fallback[axis_key])
        for axis_key in _REVIEW_SCORE_AXIS_KEYS
    }


def _score_state_snapshot() -> dict[str, int]:
    return {
        axis_key: _normalize_score_value(
            st.session_state.get(_REVIEW_SCORE_FIELD_KEYS[axis_key]),
            fallback=3,
        )
        for axis_key in _REVIEW_SCORE_AXIS_KEYS
    }


def _apply_score_state(scores: Mapping[str, object]) -> None:
    for axis_key in _REVIEW_SCORE_AXIS_KEYS:
        st.session_state[_REVIEW_SCORE_FIELD_KEYS[axis_key]] = _normalize_score_value(
            scores.get(axis_key),
            fallback=3,
        )


def _resolve_score_values(
    *,
    slider_scores: dict[str, int],
    radar_scores: dict[str, int] | None,
    baseline_scores: dict[str, int],
) -> dict[str, int]:
    if radar_scores is None:
        return slider_scores
    slider_changed = slider_scores != baseline_scores
    radar_changed = radar_scores != baseline_scores
    if radar_changed and not slider_changed:
        return radar_scores
    return slider_scores


def _is_retriable_save_error(exc: Exception) -> bool:
    error_type = exc.__class__.__name__.lower()
    if any(token in error_type for token in _REVIEWS_RETRIABLE_SAVE_ERROR_TYPES):
        return True
    message = str(exc).strip().lower()
    if not message:
        return False
    return any(hint in message for hint in _REVIEWS_RETRIABLE_SAVE_ERROR_HINTS)


def _queue_pending_save_intent_removal(intent_id: str) -> None:
    normalized_id = str(intent_id or "").strip()
    if not normalized_id:
        return
    pending_ids = [
        str(value).strip()
        for value in st.session_state.get(_REVIEWS_PENDING_SAVE_INTENT_REMOVALS_KEY, [])
        if str(value).strip()
    ]
    if normalized_id not in pending_ids:
        pending_ids.append(normalized_id)
    st.session_state[_REVIEWS_PENDING_SAVE_INTENT_REMOVALS_KEY] = pending_ids


def _queue_pending_image_upload_intent_removal(intent_id: str) -> None:
    normalized_id = str(intent_id or "").strip()
    if not normalized_id:
        return
    pending_ids = [
        str(value).strip()
        for value in st.session_state.get(_REVIEWS_PENDING_IMAGE_UPLOAD_INTENT_REMOVALS_KEY, [])
        if str(value).strip()
    ]
    if normalized_id not in pending_ids:
        pending_ids.append(normalized_id)
    st.session_state[_REVIEWS_PENDING_IMAGE_UPLOAD_INTENT_REMOVALS_KEY] = pending_ids


def _resolve_pending_save_intent() -> dict | None:
    pending = st.session_state.get(_REVIEWS_PENDING_SAVE_INTENT_KEY)
    if not isinstance(pending, dict):
        return None
    payload = pending.get("payload")
    if not isinstance(payload, dict):
        return None
    return {
        "intent_id": str(pending.get("intent_id") or "").strip(),
        "payload": dict(payload),
        "overwrite_duplicate": bool(pending.get("overwrite_duplicate")),
        "had_images": bool(pending.get("had_images")),
        "queued_at": str(pending.get("queued_at") or "").strip(),
    }


def _set_pending_save_intent(*, payload: dict, overwrite_duplicate: bool, had_images: bool) -> None:
    existing_intent = _resolve_pending_save_intent()
    existing_intent_id = existing_intent["intent_id"] if existing_intent else None
    queue_payload = {
        "payload": dict(payload),
        "overwrite_duplicate": bool(overwrite_duplicate),
        "had_images": bool(had_images),
    }
    intent_id = enqueue_offline_intent(
        _REVIEWS_SAVE_INTENT_QUEUE_KEY,
        intent_id=existing_intent_id,
        intent_type="reviews:save",
        payload=queue_payload,
        metadata={"page": "02_reviews"},
    )
    st.session_state[_REVIEWS_PENDING_SAVE_INTENT_KEY] = {
        "intent_id": intent_id,
        "payload": dict(payload),
        "overwrite_duplicate": bool(overwrite_duplicate),
        "had_images": bool(had_images),
        "queued_at": datetime.now().isoformat(timespec="seconds"),
    }


def _clear_pending_save_intent() -> None:
    pending = _resolve_pending_save_intent()
    st.session_state.pop(_REVIEWS_PENDING_SAVE_INTENT_KEY, None)
    if pending and pending.get("intent_id"):
        _queue_pending_save_intent_removal(str(pending["intent_id"]))


def _format_pending_save_timestamp(value: object) -> str:
    if value in {None, ""}:
        return "-"
    text = str(value)
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return text


def _retry_pending_save_intent() -> None:
    pending = _resolve_pending_save_intent()
    if pending is None:
        return
    trigger_offline_intent_replay(
        _REVIEWS_SAVE_INTENT_QUEUE_KEY,
        replay_event_name=_REVIEWS_SAVE_INTENT_REPLAY_EVENT,
        reason="reviews-manual-retry",
        queue_label="レビュー保存待ち",
    )
    payload = dict(pending["payload"])
    overwrite_duplicate = bool(pending.get("overwrite_duplicate"))
    try:
        review_id, _ = create_or_update_review(payload, overwrite_duplicate=overwrite_duplicate)
        _clear_pending_duplicate()
        _clear_pending_save_intent()
        st.session_state[_REVIEW_DRAFT_CLEAR_KEY] = True
        st.success("保留中のレビューを保存しました。")
        if pending.get("had_images"):
            st.info("画像がある場合は、保存後にアップロード状況を確認してください。")
        st.rerun()
    except ValueError as exc:
        if str(exc) == "DUPLICATE_REVIEW":
            st.session_state[_PENDING_DUPLICATE_PAYLOAD_KEY] = _normalize_pending_payload(payload)
            _set_pending_duplicate_files()
            st.warning("同一レビューを検出しました。上書き保存する場合は確認チェック後に実行してください。")
            return
        if _is_retriable_save_error(exc):
            st.warning("再試行中に通信が不安定です。接続回復後に再度お試しください。")
        st.error(str(exc))
    except Exception as exc:
        if _is_retriable_save_error(exc):
            st.warning("再試行中に通信が不安定です。接続回復後に再度お試しください。")
        st.error(str(exc))


def _render_pending_save_intent_notice() -> None:
    pending = _resolve_pending_save_intent()
    if pending is None:
        return
    queued_at = pending.get("queued_at")
    with st.container(border=True):
        st.warning("通信エラーによりレビュー保存を一時キューへ退避しました。")
        st.caption("接続回復後に再試行できます。")
        if queued_at:
            st.caption(f"保留時刻: {_format_pending_save_timestamp(queued_at)}")
        if pending.get("had_images"):
            st.caption("※ 画像はキューに保持されないため、再試行後に必要なら再添付してください。")
        retry_col, cancel_col = st.columns([1.35, 1], gap="small")
        with retry_col:
            retry_requested = st.button(
                "保留中の保存を再試行",
                key=f"reviews_retry_pending_intent_{pending['intent_id'] or 'latest'}",
                type="primary",
                use_container_width=True,
            )
        with cancel_col:
            cancel_requested = st.button(
                "保留を取り消す",
                key=f"reviews_cancel_pending_intent_{pending['intent_id'] or 'latest'}",
                type="secondary",
                use_container_width=True,
            )
    if retry_requested:
        _retry_pending_save_intent()
    if cancel_requested:
        _clear_pending_save_intent()
        st.info("保留中の保存を取り消しました。")
        st.rerun()


def _inject_mobile_bottom_sheet_style() -> None:
    st.markdown(
        """
        <style>
        @media (max-width: 820px) {
            .reviews-mobile-sheet-anchor + div[data-testid="stHorizontalBlock"] {
                z-index: 64;
            }
            .reviews-mobile-sheet-anchor + div[data-testid="stHorizontalBlock"] [data-testid="stPopover"] > button {
                min-height: 56px !important;
                border-radius: 12px !important;
                width: 100%;
                border: 1px solid var(--sl-border-strong) !important;
                background: #ffffff !important;
                font-weight: 700 !important;
                margin-bottom: 0 !important;
            }
            [data-testid="stPopoverContent"],
            div[data-baseweb="popover"] {
                position: fixed !important;
                left: 0.55rem !important;
                right: 0.55rem !important;
                top: auto !important;
                bottom: calc(var(--sl-safe-bottom) + 4.8rem) !important;
                width: auto !important;
                max-height: min(72vh, 660px) !important;
                border-radius: 18px 18px 14px 14px !important;
                border: 1px solid var(--sl-border) !important;
                box-shadow: 0 -10px 28px rgba(17, 24, 39, 0.22) !important;
                overflow-y: auto !important;
                transform: none !important;
                z-index: 70 !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


st.set_page_config(page_title="試食評価", layout="wide")
require_admin_session()
inject_app_style()
render_sidebar(active_page="reviews")
render_primary_nav(active_page="reviews")
render_hero_banner(
    "試食評価",
    "登録・履歴確認・削除復元まで、試食レビュー運用を一画面で管理できます。",
    eyebrow="レビュー運用",
    chips=["日本語UI最適化", "重複上書き対応", "画像なし保存OK"],
)
render_action_bar(
    title="入力から運用までをシンプルに",
    description="必須入力は最小限、重複時は上書き確認付きで安全に保存します。",
    actions=["作成・編集", "履歴管理", "削除復元"],
)
active_varieties = list_active_varieties()
mobile_client = is_mobile_client()
if mobile_client:
    _inject_mobile_bottom_sheet_style()
pending_save_intent_removals = [
    str(value).strip()
    for value in st.session_state.pop(_REVIEWS_PENDING_SAVE_INTENT_REMOVALS_KEY, [])
    if str(value).strip()
]
for pending_intent_id in pending_save_intent_removals:
    remove_offline_intent(_REVIEWS_SAVE_INTENT_QUEUE_KEY, pending_intent_id)
pending_image_upload_intent_removals = [
    str(value).strip()
    for value in st.session_state.pop(_REVIEWS_PENDING_IMAGE_UPLOAD_INTENT_REMOVALS_KEY, [])
    if str(value).strip()
]
for pending_intent_id in pending_image_upload_intent_removals:
    remove_offline_intent(_REVIEWS_IMAGE_UPLOAD_QUEUE_KEY, pending_intent_id)
render_offline_intent_queue_bridge(
    _REVIEWS_SAVE_INTENT_QUEUE_KEY,
    queue_label="レビュー保存待ち",
    replay_event_name=_REVIEWS_SAVE_INTENT_REPLAY_EVENT,
    show_replay_button=False,
    auto_replay_on_online=True,
)
render_offline_intent_queue_bridge(
    _REVIEWS_IMAGE_UPLOAD_QUEUE_KEY,
    queue_label="レビュー画像アップロード待ち",
    replay_event_name=_REVIEWS_IMAGE_UPLOAD_REPLAY_EVENT,
    show_replay_button=False,
    auto_replay_on_online=True,
)

tab_edit, tab_history, tab_deleted = st.tabs(["レビュー登録", "履歴管理", "削除済み復元"])

with tab_edit:
    clear_review_draft_before_restore = bool(st.session_state.pop(_REVIEW_DRAFT_CLEAR_KEY, False))
    with st.container(border=True):
        render_section_title("評価登録", "必須項目を入力すると総合スコアを自動算出して保存できます。")
        _render_pending_save_intent_notice()
        st.caption("入力内容はブラウザに自動保存されます。")
        if st.session_state.pop(_REVIEW_DRAFT_DISCARD_NOTICE_KEY, False):
            st.caption("🗑️ 下書きを破棄しました。")
        varieties = active_varieties
        variety_names = _variety_name_map(varieties)
        if not varieties:
            if clear_review_draft_before_restore:
                clear_draft_buffer(_REVIEW_DRAFT_KEY)
            render_empty_state(
                f"{EMPTY_STATE_MESSAGE} 先に「品種管理」で品種を登録してください。",
                title="品種が未登録です",
                action_label="🍓 品種管理を開く",
                action_path="pages/01_varieties.py",
            )
        else:
            variety_options = [v["id"] for v in varieties]
            query_variety_id = resolve_review_variety_query_param(st.query_params)
            if query_variety_id in variety_options:
                st.session_state["review_variety_id"] = query_variety_id
            if st.session_state.get("review_variety_id") not in variety_options:
                st.session_state["review_variety_id"] = variety_options[0]
            pending_image_upload = _resolve_pending_image_upload()
            uploader_state = render_asset_uploader(
                key=_REVIEW_ASSET_UPLOADER_KEY,
                max_files=3,
                label="画像アップロード（最大3枚）",
                height=410,
                upload_targets=pending_image_upload.get("targets") if pending_image_upload else None,
                upload_request_token=pending_image_upload.get("token") if pending_image_upload else "",
                clear_token=str(st.session_state.get(_REVIEWS_ASSET_CLEAR_TOKEN_KEY) or ""),
                replay_event_name=_REVIEWS_IMAGE_UPLOAD_REPLAY_EVENT,
                replay_queue_key=_REVIEWS_IMAGE_UPLOAD_QUEUE_KEY,
            )
            uploader_component_available = bool(uploader_state.get("component_available"))
            component_files_to_upload = _collect_component_upload_files(uploader_state)
            if uploader_component_available:
                st.caption("画像はブラウザ側で最適化され、レビュー保存後にSupabase Storageへ直接アップロードされます。")
            else:
                st.caption("カスタム画像アップローダーを読み込めないため、標準アップロードへフォールバックします。")

            if pending_image_upload:
                can_cancel_pending_upload = False
                cancel_button_key = "reviews_cancel_pending_image_upload"
                if not uploader_component_available:
                    st.warning("保留中の画像アップロードを再開するにはカスタム画像アップローダーの読み込みが必要です。")
                    can_cancel_pending_upload = True
                    cancel_button_key = "reviews_cancel_pending_image_upload_unavailable"
                else:
                    pending_token = str(pending_image_upload["token"])
                    expected_count = int(pending_image_upload["expected_count"])
                    uploaded_entries = [
                        entry
                        for entry in (uploader_state.get("uploaded") or [])
                        if str(entry.get("upload_request_token") or "") == pending_token
                    ]
                    failed_entries = [
                        entry
                        for entry in (uploader_state.get("failed") or [])
                        if str(entry.get("upload_request_token") or "") == pending_token
                    ]
                    if str(uploader_state.get("last_processed_upload_token") or "") == pending_token:
                        if failed_entries:
                            st.error("画像アップロードに失敗したファイルがあります。再試行後に処理が完了します。")
                            can_cancel_pending_upload = True
                        elif expected_count and len(uploaded_entries) >= expected_count:
                            try:
                                finalize_review_image_direct_uploads(pending_image_upload["review_id"], uploaded_entries)
                                _clear_pending_image_upload()
                                st.session_state[_REVIEWS_ASSET_CLEAR_TOKEN_KEY] = str(uuid4())
                                st.success(str(pending_image_upload["success_message"]))
                                st.rerun()
                            except Exception as exc:
                                st.warning("レビューは保存済みですが、画像メタデータ確定でエラーが発生しました。")
                                st.error(str(exc))
                                can_cancel_pending_upload = True
                        else:
                            st.warning("画像アップロード結果を確認できませんでした。再試行後に解消しない場合は取り消してください。")
                            can_cancel_pending_upload = True
                    else:
                        st.caption("画像アップロードを処理中です。完了まで少しお待ちください。")
                if can_cancel_pending_upload and st.button(
                    "画像アップロード待ちを取り消す",
                    key=cancel_button_key,
                    use_container_width=True,
                    type="secondary",
                ):
                    _clear_pending_image_upload()
                    st.session_state[_REVIEWS_ASSET_CLEAR_TOKEN_KEY] = str(uuid4())
                    st.rerun()
            with st.form("review_entry_form", clear_on_submit=False):
                purchase_place = str(st.session_state.get("review_purchase_place") or "")
                price_jpy = int(st.session_state.get("review_price_jpy") or 0)
                comment = str(st.session_state.get("review_comment") or "")
                uploaded_files = st.session_state.get("review_uploaded_files")
                st.caption("※ * は必須項目です。任意項目は空欄でも保存できます。")
                st.markdown("##### 1) 試食情報")
                variety_id = st.selectbox(
                    "品種 *",
                    variety_options,
                    format_func=lambda x: variety_names.get(str(x), str(x)),
                    key="review_variety_id",
                )
                tasted_date = st.date_input(
                    "試食日 *",
                    value=date.today(),
                    max_value=date.today(),
                    key="review_tasted_date",
                )
                if mobile_client:
                    st.caption("購入場所・価格は下部の「任意入力シート」から追加できます。")
                else:
                    purchase_place = st.text_input("購入場所", key="review_purchase_place")
                    price_jpy = st.number_input(
                        "価格（円）",
                        min_value=0,
                        max_value=1_000_000,
                        value=0,
                        step=10,
                        key="review_price_jpy",
                    )

                st.markdown("##### 2) 味覚スコア（必須）")
                if mobile_client:
                    st.caption("モバイルではレーダーを標準表示しています。ドラッグで調整し、必要に応じて下のスライダーで微調整できます。")
                else:
                    st.caption("レーダー入力（ドラッグ）と従来スライダー入力を併用できます。操作しやすい方で入力してください。")
                st.caption(f"スコア目安: {_SCORE_GUIDE_TEXT}")
                st.caption("※ レーダーが表示されない場合でも、下のスライダー入力でそのまま保存できます。")
                slider_scores_from_state = _score_state_snapshot()
                baseline_scores = _coerce_score_map(
                    st.session_state.get(_REVIEW_SCORE_BASELINE_KEY),
                    fallback=slider_scores_from_state,
                )
                radar_scores = _coerce_score_map(
                    render_radar_input(
                        key="review_score_radar",
                        value=slider_scores_from_state,
                        axis_keys=_REVIEW_SCORE_AXIS_KEYS,
                        axis_labels=_REVIEW_SCORE_RADAR_LABELS,
                        min_value=1,
                        max_value=5,
                        default_value=3,
                        step=1,
                        height=320 if mobile_client else 360,
                        use_native_fallback=False,
                    ),
                    fallback=slider_scores_from_state,
                )
                resolved_scores = _resolve_score_values(
                    slider_scores=slider_scores_from_state,
                    radar_scores=radar_scores,
                    baseline_scores=baseline_scores,
                )
                if resolved_scores != slider_scores_from_state:
                    _apply_score_state(resolved_scores)
                sweetness = st.slider("甘味 *", 1, 5, 3, key="review_sweetness", help=_SCORE_GUIDE_TEXT)
                sourness = st.slider("酸味 *", 1, 5, 3, key="review_sourness", help=_SCORE_GUIDE_TEXT)
                aroma = st.slider("香り *", 1, 5, 3, key="review_aroma", help=_SCORE_GUIDE_TEXT)
                texture = st.slider("食感 *", 1, 5, 3, key="review_texture", help=_SCORE_GUIDE_TEXT)
                appearance = st.slider("見た目 *", 1, 5, 3, key="review_appearance", help=_SCORE_GUIDE_TEXT)
                score_snapshot = {
                    "sweetness": sweetness,
                    "sourness": sourness,
                    "aroma": aroma,
                    "texture": texture,
                    "appearance": appearance,
                }
                st.session_state[_REVIEW_SCORE_BASELINE_KEY] = score_snapshot.copy()
                st.caption(
                    "現在値: "
                    f"甘味 {sweetness}/5（{_score_level_label(sweetness)}）・"
                    f"酸味 {sourness}/5（{_score_level_label(sourness)}）・"
                    f"香り {aroma}/5（{_score_level_label(aroma)}）・"
                    f"食感 {texture}/5（{_score_level_label(texture)}）・"
                    f"見た目 {appearance}/5（{_score_level_label(appearance)}）"
                )
                overall = max(
                    1,
                    min(
                        10,
                        int(
                            round(
                                (
                                    sweetness
                                    + sourness
                                    + aroma
                                    + texture
                                    + appearance
                                )
                                / 5
                                * 2
                            )
                        ),
                    ),
                )
                render_kpi_cards([("総合スコア（自動）", f"{overall}/10", "5項目平均から算出")])

                st.markdown("##### 3) コメント・画像（任意）")
                if mobile_client:
                    render_status_badge("任意項目は下部の入力シートからまとめて編集できます", tone="info")
                else:
                    comment = st.text_area("コメント", height=140, key="review_comment")
                    if not uploader_component_available:
                        uploaded_files = st.file_uploader(
                            "画像アップロード（最大3枚）",
                            type=["jpg", "jpeg", "png", "webp"],
                            accept_multiple_files=True,
                            key="review_uploaded_files",
                        )
                        if uploaded_files:
                            preview_targets = uploaded_files[:3]
                            st.image(
                                [file.getvalue() for file in preview_targets],
                                caption=[file.name for file in preview_targets],
                                use_container_width=True,
                            )
                if uploader_component_available:
                    current_upload_count = len(component_files_to_upload)
                else:
                    current_upload_count = len(st.session_state.get("review_uploaded_files") or uploaded_files or [])

                selected_name = variety_names.get(str(variety_id), str(variety_id))
                render_surface(
                    f"品種: **{selected_name}** / "
                    f"試食日: **{tasted_date}** / "
                    f"総合スコア: **{overall}/10** / "
                    f"画像枚数: **{current_upload_count}枚**",
                    title="保存前サマリー",
                    subtitle="必須: 品種・試食日・5項目スコア",
                    tone="soft",
                )
                render_status_badge("任意項目（購入場所・価格・コメント・画像）は後から追記可能", tone="info")
                st.page_link("pages/01_varieties.py", label="🍓 品種情報を確認", use_container_width=True)
                if mobile_client:
                    st.markdown(
                        '<div class="sl-bottom-nav-anchor reviews-mobile-sheet-anchor" aria-hidden="true"></div>',
                        unsafe_allow_html=True,
                    )
                    sheet_col, submit_col = st.columns([1.35, 1], gap="small")
                    with sheet_col:
                        with st.popover("📝 任意入力シート"):
                            purchase_place = st.text_input("購入場所", key="review_purchase_place")
                            price_jpy = st.number_input(
                                "価格（円）",
                                min_value=0,
                                max_value=1_000_000,
                                value=0,
                                step=10,
                                key="review_price_jpy",
                            )
                            comment = st.text_area("コメント", height=140, key="review_comment")
                            if not uploader_component_available:
                                uploaded_files = st.file_uploader(
                                    "画像アップロード（最大3枚）",
                                    type=["jpg", "jpeg", "png", "webp"],
                                    accept_multiple_files=True,
                                    key="review_uploaded_files",
                                )
                                if uploaded_files:
                                    preview_targets = uploaded_files[:3]
                                    st.image(
                                        [file.getvalue() for file in preview_targets],
                                        caption=[file.name for file in preview_targets],
                                        use_container_width=True,
                                    )
                            st.caption("保存する場合は右の「この内容で保存」をタップしてください。")
                    with submit_col:
                        submit = st.form_submit_button(
                            "この内容で保存",
                            use_container_width=True,
                            type="primary",
                            disabled=bool(pending_image_upload),
                        )
                else:
                    render_sticky_primary_action_anchor("reviews-save")
                    submit = st.form_submit_button(
                        "この内容で保存",
                        use_container_width=True,
                        type="primary",
                        disabled=bool(pending_image_upload),
                    )

            if submit:
                payload = {
                    "variety_id": variety_id,
                    "tasted_date": tasted_date,
                    "sweetness": sweetness,
                    "sourness": sourness,
                    "aroma": aroma,
                    "texture": texture,
                    "appearance": appearance,
                    "overall": overall,
                    "purchase_place": purchase_place,
                    "price_jpy": price_jpy,
                    "comment": comment,
                }
                component_upload_files = component_files_to_upload if uploader_component_available else []
                fallback_files_to_upload = _collect_upload_files(uploaded_files) if not uploader_component_available else []
                has_images = bool(component_upload_files or fallback_files_to_upload)
                try:
                    review_id, _ = create_or_update_review(payload)
                except ValueError as exc:
                    if str(exc) == "DUPLICATE_REVIEW":
                        _clear_pending_save_intent()
                        st.session_state[_PENDING_DUPLICATE_PAYLOAD_KEY] = _normalize_pending_payload(payload)
                        _set_pending_duplicate_files(
                            component_files=component_upload_files,
                            fallback_files=fallback_files_to_upload,
                        )
                    else:
                        _clear_pending_duplicate()
                        if _is_retriable_save_error(exc):
                            _set_pending_save_intent(
                                payload=payload,
                                overwrite_duplicate=False,
                                had_images=has_images,
                            )
                            st.warning("通信エラーのため保存要求をキューに退避しました。接続回復後に再試行してください。")
                        st.error(str(exc))
                except Exception as exc:
                    _clear_pending_duplicate()
                    if _is_retriable_save_error(exc):
                        _set_pending_save_intent(
                            payload=payload,
                            overwrite_duplicate=False,
                            had_images=has_images,
                        )
                        st.warning("通信エラーのため保存要求をキューに退避しました。接続回復後に再試行してください。")
                    st.error(str(exc))
                else:
                    _clear_pending_duplicate()
                    _clear_pending_save_intent()
                    try:
                        if uploader_component_available:
                            targets = prepare_review_image_direct_upload_targets(review_id, component_upload_files)
                            if targets:
                                _set_pending_image_upload(
                                    review_id=review_id,
                                    targets=targets,
                                    success_message="保存しました。",
                                )
                                st.session_state[_REVIEW_DRAFT_CLEAR_KEY] = True
                                st.rerun()
                        else:
                            _upload_review_images(review_id, fallback_files_to_upload)
                    except Exception as exc:
                        st.warning("レビューは保存しましたが、画像処理でエラーが発生しました。")
                        st.error(str(exc))
                    else:
                        st.session_state[_REVIEWS_ASSET_CLEAR_TOKEN_KEY] = str(uuid4())
                        st.session_state[_REVIEW_DRAFT_CLEAR_KEY] = True
                        st.success("保存しました。")
                        st.rerun()

            render_draft_buffer_bridge(
                _REVIEW_DRAFT_KEY,
                fields=_REVIEW_DRAFT_FIELDS,
                notice_message="保存前のレビュー下書きを復元しました。",
                clear_before_restore=clear_review_draft_before_restore,
            )

            pending_payload = st.session_state.get(_PENDING_DUPLICATE_PAYLOAD_KEY)
            if pending_payload:
                pending_variety = variety_names.get(
                    str(pending_payload["variety_id"]),
                    str(pending_payload["variety_id"]),
                )
                render_surface(
                    f"同じ品種・試食日のレビューが存在します（{pending_variety} / {pending_payload['tasted_date']}）。\n\n"
                    "上書き保存する場合は、確認チェック後に実行してください。",
                    title="重複レビューを検出しました",
                    tone="accent",
                )
                overwrite_confirm_key = (
                    f"confirm_overwrite_review_{pending_payload['variety_id']}_{pending_payload['tasted_date']}"
                )
                overwrite_confirmed = st.checkbox(
                    "既存記録を上書きすることを確認しました",
                    key=overwrite_confirm_key,
                )
                if st.button(
                    "既存記録を上書き保存する",
                    key="overwrite_review",
                    use_container_width=True,
                    type="secondary",
                    disabled=not overwrite_confirmed,
                ):
                    pending_component_files, pending_fallback_files = _resolve_pending_duplicate_files()
                    has_pending_images = bool(pending_component_files or pending_fallback_files)
                    try:
                        review_id, _ = create_or_update_review(
                            pending_payload,
                            overwrite_duplicate=True,
                        )
                    except Exception as exc:
                        if _is_retriable_save_error(exc):
                            _set_pending_save_intent(
                                payload=pending_payload,
                                overwrite_duplicate=True,
                                had_images=has_pending_images,
                            )
                            st.warning("通信エラーのため上書き保存要求をキューに退避しました。接続回復後に再試行してください。")
                        st.error(str(exc))
                    else:
                        _clear_pending_duplicate()
                        _clear_pending_save_intent()
                        try:
                            if uploader_component_available and pending_component_files:
                                targets = prepare_review_image_direct_upload_targets(review_id, pending_component_files)
                                if targets:
                                    _set_pending_image_upload(
                                        review_id=review_id,
                                        targets=targets,
                                        success_message="既存記録を更新しました。",
                                    )
                                    st.session_state[_REVIEW_DRAFT_CLEAR_KEY] = True
                                    st.rerun()
                            if pending_fallback_files:
                                _upload_review_images(review_id, pending_fallback_files)
                            elif pending_component_files and not uploader_component_available:
                                st.warning(
                                    "画像アップローダーを読み込めないため、上書き時の画像は保存されませんでした。必要に応じて再添付してください。"
                                )
                        except Exception as exc:
                            st.warning("レビューは更新しましたが、画像処理でエラーが発生しました。")
                            st.error(str(exc))
                        else:
                            st.session_state[_REVIEWS_ASSET_CLEAR_TOKEN_KEY] = str(uuid4())
                            st.session_state[_REVIEW_DRAFT_CLEAR_KEY] = True
                            st.success("既存記録を更新しました。")
                            st.rerun()
                if st.button(
                    "上書きを取り消す",
                    key="cancel_overwrite_review",
                    use_container_width=True,
                    type="secondary",
                ):
                    _clear_pending_duplicate()
                    st.info("上書きをキャンセルしました。")
                    st.rerun()

            discard_col, discard_hint_col = st.columns([1, 2], gap="small")
            with discard_col:
                discard_draft = st.button(
                    "下書きを破棄",
                    key="reviews_discard_draft",
                    use_container_width=True,
                    type="secondary",
                )
            with discard_hint_col:
                st.caption("ブラウザに保存された入力中の下書きを削除します。")
            if discard_draft:
                _clear_pending_duplicate()
                _clear_pending_image_upload()
                st.session_state[_REVIEWS_ASSET_CLEAR_TOKEN_KEY] = str(uuid4())
                st.session_state[_REVIEW_DRAFT_CLEAR_KEY] = True
                st.session_state[_REVIEW_DRAFT_DISCARD_NOTICE_KEY] = True
                st.rerun()

@st.fragment
def _render_reviews_history_fragment() -> None:
    with st.container(border=True):
        render_section_title("評価履歴", "フィルタで絞り込み、内容確認や削除操作を行えます。")
        varieties = active_varieties
        variety_names = _variety_name_map(varieties)
        f1, f2, f3 = st.columns(3, gap="large")
        with f1:
            variety_filter = st.selectbox(
                "品種フィルタ",
                [""] + [v["id"] for v in varieties],
                format_func=lambda x: "すべて" if not x else variety_names.get(str(x), str(x)),
            )
        with f2:
            date_from = st.date_input("開始日", value=date.today().replace(day=1), key="reviews_from")
        with f3:
            date_to = st.date_input("終了日", value=date.today(), key="reviews_to")

    if date_from > date_to:
        st.error("開始日は終了日以前で指定してください。")
        return

    page, page_size = render_pagination_controls("reviews_history")
    rows, total = list_reviews(
        variety_id=variety_filter or None,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
    with st.container(border=True):
        render_kpi_cards(
            [
                ("ヒット件数", str(total), "検索条件に一致した総件数"),
                ("現在ページ", str(len(rows)), f"{page_size}件表示設定"),
            ]
        )
        if rows:
            render_table(rows)
        else:
            render_empty_state(
                "条件に一致するレビューはありません。",
                title="検索結果がありません",
                hint="フィルタを調整して再検索してください。",
            )

    with st.container(border=True):
        render_section_title("履歴アクション", "表示中のレビューから削除対象を選択します。")
        delete_col, delete_action_col = st.columns([2, 1], gap="medium")
        with delete_col:
            delete_id = st.selectbox(
                "削除対象",
                [""] + [r["id"] for r in rows],
                format_func=lambda x: next(
                    (f"{r['tasted_date']} {r['id'][:8]}" for r in rows if r["id"] == x),
                    "未選択",
                ),
                key="reviews_delete_select",
            )
            delete_confirm_key = f"reviews_delete_confirm_{delete_id or 'none'}"
            delete_confirmed = st.checkbox(
                "選択したレビューを削除することを確認しました",
                key=delete_confirm_key,
                disabled=not delete_id,
            )
        with delete_action_col:
            delete_clicked = st.button(
                "選択したレビューを削除",
                key="delete_review_action",
                use_container_width=True,
                disabled=not (delete_id and delete_confirmed),
                type="secondary",
            )
    if delete_clicked:
        soft_delete_review(delete_id)
        st.success("削除しました。")
        st.rerun()


@st.fragment
def _render_reviews_deleted_fragment() -> None:
    with st.container(border=True):
        render_section_title("削除済みレビュー", "復元可能なレビューを確認し、必要に応じて戻します。")
        page, page_size = render_pagination_controls("reviews_deleted")
        rows, _ = list_reviews(include_deleted=True, page=page, page_size=page_size)
        deleted_rows = [row for row in rows if row.get("deleted_at")]
        render_kpi_cards([("削除済み件数", str(len(deleted_rows)), "現在ページで表示中")])
        if deleted_rows:
            render_table(deleted_rows)
        else:
            render_empty_state("このページに削除済みレビューはありません。", title="復元対象がありません")

    with st.container(border=True):
        restore_col, restore_action_col = st.columns([2, 1], gap="medium")
        with restore_col:
            restore_id = st.selectbox(
                "復元対象",
                [""] + [r["id"] for r in deleted_rows],
                format_func=lambda x: next(
                    (f"{r['tasted_date']} {r['id'][:8]}" for r in deleted_rows if r["id"] == x),
                    "未選択",
                ),
                key="reviews_restore_select",
            )
        with restore_action_col:
            restore_clicked = st.button(
                "選択したレビューを復元",
                key="restore_review",
                use_container_width=True,
                disabled=not restore_id,
                type="primary",
            )
    if restore_clicked:
        try:
            restore_review(restore_id)
            st.success("復元しました。")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


with tab_history:
    _render_reviews_history_fragment()

with tab_deleted:
    _render_reviews_deleted_fragment()
