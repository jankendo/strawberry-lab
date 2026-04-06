"""Table rendering helpers."""

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


def _format_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    formatted = df.copy()
    for column in formatted.columns:
        formatted[column] = formatted[column].apply(
            lambda value: " | ".join(value) if isinstance(value, list) else value
        )
        if column in _DATETIME_COLUMNS:
            formatted[column] = formatted[column].apply(_format_datetime)
        elif column in _DATE_COLUMNS:
            formatted[column] = formatted[column].apply(_format_date)
        elif column == "status":
            formatted[column] = formatted[column].apply(_format_status)
        elif column.endswith("_url"):
            formatted[column] = formatted[column].apply(lambda value: "🔗 リンク" if value else "-")
    formatted = formatted.rename(columns={col: COLUMN_LABELS.get(col, col) for col in formatted.columns})
    return formatted


def render_table(data: list[dict], *, use_container_width: bool = True) -> None:
    """Render data table with consistent empty-state handling."""
    if not data:
        st.info(EMPTY_STATE_MESSAGE)
        return
    st.dataframe(_format_dataframe(pd.DataFrame(data)), use_container_width=use_container_width, hide_index=True)
