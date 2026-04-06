"""Table and mobile card-list rendering helpers."""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from src.constants.ui import EMPTY_STATE_MESSAGE

COLUMN_LABELS = {
    "id": "ID",
    "name": "品種名",
    "registration_number": "登録番号",
    "application_number": "出願番号",
    "registration_date": "登録年月日",
    "application_date": "出願年月日",
    "publication_date": "出願公表年月日",
    "scientific_name": "学名",
    "japanese_name": "和名",
    "breeder_right_holder": "育成者権者",
    "applicant": "出願者",
    "breeding_place": "育成地",
    "characteristics_summary": "特性概要",
    "right_duration": "権利存続期間",
    "usage_conditions": "利用条件",
    "remarks": "備考",
    "origin_prefecture": "都道府県",
    "developer": "開発者",
    "registered_year": "登録年",
    "description": "説明",
    "tasted_date": "試食日",
    "sweetness": "甘味",
    "sourness": "酸味",
    "aroma": "香り",
    "texture": "食感",
    "appearance": "見た目",
    "overall": "総合評価",
    "purchase_place": "購入場所",
    "price_jpy": "価格(円)",
    "comment": "コメント",
    "title": "タイトル",
    "body": "本文",
    "tags": "タグ",
    "status": "状態",
    "started_at": "開始日時",
    "finished_at": "終了日時",
    "listed_count": "一覧件数",
    "processed_count": "処理件数",
    "upserted_count": "反映件数",
    "failed_count": "失敗件数",
    "error_message": "エラー内容",
    "variety_name": "品種名",
    "detail_url": "詳細URL",
    "created_at": "作成日時",
    "updated_at": "更新日時",
    "deleted_at": "削除日時",
}


_DATETIME_COLUMNS = {"started_at", "finished_at", "created_at", "updated_at", "deleted_at"}
_DATE_COLUMNS = {"registration_date", "application_date", "publication_date", "tasted_date"}
_STATUS_ICON = {
    "success": "✅",
    "succeeded": "✅",
    "completed": "✅",
    "done": "✅",
    "running": "⏳",
    "in_progress": "⏳",
    "queued": "⏳",
    "pending": "⏳",
    "warning": "⚠️",
    "partial": "⚠️",
    "failed": "❗",
    "error": "❗",
    "cancelled": "❗",
    "canceled": "❗",
}

_MOBILE_USER_AGENT_TOKENS = (
    "android",
    "iphone",
    "ipad",
    "ipod",
    "mobile",
    "windows phone",
)
_VERBOSE_METADATA_KEYS = {
    "description",
    "comment",
    "body",
    "characteristics_summary",
    "remarks",
    "error_message",
    "説明",
    "コメント",
    "本文",
    "特性概要",
    "備考",
    "エラー内容",
}
_DEFAULT_METADATA_LIMIT = 4


def _format_datetime(value: object) -> object:
    if value in {None, ""}:
        return "-"
    text = str(value)
    try:
        normalized = text.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        return text
    return dt.strftime("%Y-%m-%d %H:%M")


def _format_date(value: object) -> object:
    if value in {None, ""}:
        return "-"
    text = str(value)
    return text[:10]


def _format_status(value: object) -> object:
    if value in {None, ""}:
        return "-"
    normalized = str(value).strip().lower()
    icon = _STATUS_ICON.get(normalized, "ℹ️")
    return f"{icon} {value}"


def _format_cell_value(column: str, value: object) -> object:
    if isinstance(value, list):
        value = " | ".join(str(item) for item in value)
    if column in _DATETIME_COLUMNS:
        return _format_datetime(value)
    if column in _DATE_COLUMNS:
        return _format_date(value)
    if column == "status":
        return _format_status(value)
    if column.endswith("_url"):
        return "🔗 リンク" if value else "-"
    if value in {None, ""}:
        return "-"
    return value


def _format_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    formatted_rows: list[dict[str, object]] = []
    for row in rows:
        formatted_row: dict[str, object] = {}
        for column, value in row.items():
            formatted_row[COLUMN_LABELS.get(column, column)] = _format_cell_value(column, value)
        formatted_rows.append(formatted_row)
    return formatted_rows


def _format_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    return pd.DataFrame(_format_rows(df.to_dict(orient="records")))


def _coerce_bool(value: object | None) -> bool | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on", "y"}:
        return True
    if normalized in {"0", "false", "no", "off", "n"}:
        return False
    return None


def _query_param_mobile_override() -> bool | None:
    try:
        raw = st.query_params.get("mobile")
    except Exception:
        return None
    if isinstance(raw, list):
        raw = raw[0] if raw else None
    return _coerce_bool(raw)


def _read_user_agent() -> str:
    try:
        context = getattr(st, "context", None)
        if context is None:
            return ""
        headers = getattr(context, "headers", None)
        if headers is None:
            return ""
        if isinstance(headers, dict):
            return str(headers.get("user-agent") or headers.get("User-Agent") or "")
        if hasattr(headers, "get"):
            return str(headers.get("user-agent", "") or headers.get("User-Agent", ""))
    except Exception:
        return ""
    return ""


def is_mobile_client() -> bool:
    """Return True when current request is likely from a mobile client."""
    override = _query_param_mobile_override()
    if override is not None:
        return override
    user_agent = _read_user_agent().lower()
    return any(token in user_agent for token in _MOBILE_USER_AGENT_TOKENS)


def _as_display_key(column: str | None) -> str | None:
    if not column:
        return None
    return COLUMN_LABELS.get(column, column)


def _card_text(value: object) -> str:
    if value is None:
        return "-"
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return "-"
    return text


def _resolve_card_title_key(rows: list[dict], title_key: str | None) -> str | None:
    if not rows:
        return None
    first_row = rows[0]
    if title_key and title_key in first_row:
        return title_key
    for candidate in ("品種名", "タイトル", "状態", "name", "title", "status", "ID", "id"):
        if candidate in first_row:
            return candidate
    return next(iter(first_row), None)


def _resolve_card_subtitle_key(rows: list[dict], subtitle_key: str | None, title_key: str | None) -> str | None:
    if not rows:
        return None
    first_row = rows[0]
    if subtitle_key and subtitle_key in first_row and subtitle_key != title_key:
        return subtitle_key
    for candidate in ("試食日", "開始日時", "作成日時", "更新日時", "tasted_date", "started_at", "created_at"):
        if candidate in first_row and candidate != title_key:
            return candidate
    return None


def _build_metadata_items(
    row: dict[str, object],
    *,
    title_key: str | None,
    subtitle_key: str | None,
    metadata_keys: list[str] | None,
) -> list[tuple[str, str]]:
    explicit_keys = metadata_keys is not None
    candidate_keys = (
        metadata_keys
        if metadata_keys is not None
        else [
            key
            for key in row
            if key not in {title_key, subtitle_key}
            and key not in _VERBOSE_METADATA_KEYS
        ]
    )

    items: list[tuple[str, str]] = []
    for key in candidate_keys:
        if key not in row or key in {title_key, subtitle_key}:
            continue
        value_text = _card_text(row.get(key))
        if value_text == "-":
            continue
        if not explicit_keys and len(value_text) > 48:
            continue
        items.append((key, value_text))
        if not explicit_keys and len(items) >= _DEFAULT_METADATA_LIMIT:
            break
    return items


def render_card_list(
    rows: list[dict],
    *,
    title_key: str | None = None,
    subtitle_key: str | None = None,
    metadata_keys: list[str] | None = None,
    tap_action_label: str | None = None,
    tap_action_state_key: str | None = None,
    tap_action_value_key: str | None = None,
) -> object | None:
    """Render compact card rows for mobile-friendly list browsing."""
    if not rows:
        st.info(EMPTY_STATE_MESSAGE)
        return None

    resolved_title_key = _resolve_card_title_key(rows, title_key)
    resolved_subtitle_key = _resolve_card_subtitle_key(rows, subtitle_key, resolved_title_key)
    selected_value: object | None = None

    for index, row in enumerate(rows):
        title_text = _card_text(row.get(resolved_title_key)) if resolved_title_key else "-"
        subtitle_text = _card_text(row.get(resolved_subtitle_key)) if resolved_subtitle_key else "-"
        metadata_items = _build_metadata_items(
            row,
            title_key=resolved_title_key,
            subtitle_key=resolved_subtitle_key,
            metadata_keys=metadata_keys,
        )

        with st.container(border=True):
            st.markdown(f"**{title_text}**")
            if subtitle_text != "-":
                st.caption(subtitle_text)

            for start in range(0, len(metadata_items), 2):
                chunk = metadata_items[start : start + 2]
                columns = st.columns(len(chunk), gap="small")
                for column, (label, value) in zip(columns, chunk, strict=True):
                    with column:
                        st.caption(label)
                        st.markdown(value)

            if tap_action_label:
                tap_value = (
                    row.get(tap_action_value_key)
                    if tap_action_value_key and tap_action_value_key in row
                    else row.get(resolved_title_key) if resolved_title_key else index
                )
                try:
                    button_label = tap_action_label.format(title=title_text)
                except (KeyError, ValueError):
                    button_label = tap_action_label
                button_key = (
                    f"mobile_card_tap_{tap_action_state_key or 'default'}_{index}"
                    f"_{str(tap_value)}"
                )
                if st.button(button_label, key=button_key, use_container_width=True, type="secondary"):
                    selected_value = tap_value
                    if tap_action_state_key:
                        st.session_state[tap_action_state_key] = tap_value

    return selected_value


def render_table(
    data: list[dict],
    *,
    use_container_width: bool = True,
    mobile_title_key: str | None = None,
    mobile_subtitle_key: str | None = None,
    mobile_metadata_keys: list[str] | None = None,
    mobile_tap_action_label: str | None = None,
    mobile_tap_action_state_key: str | None = None,
    mobile_tap_action_value_key: str | None = None,
) -> object | None:
    """Render desktop tables and mobile card-lists with shared formatting."""
    if not data:
        st.info(EMPTY_STATE_MESSAGE)
        return None

    if is_mobile_client():
        return render_card_list(
            _format_rows(data),
            title_key=_as_display_key(mobile_title_key),
            subtitle_key=_as_display_key(mobile_subtitle_key),
            metadata_keys=[_as_display_key(key) or key for key in (mobile_metadata_keys or [])] or None,
            tap_action_label=mobile_tap_action_label,
            tap_action_state_key=mobile_tap_action_state_key,
            tap_action_value_key=_as_display_key(mobile_tap_action_value_key),
        )

    formatted = _format_dataframe(pd.DataFrame(data))
    formatted = formatted.where(pd.notna(formatted), "-")
    st.dataframe(formatted, use_container_width=use_container_width, hide_index=True)
    return None
