"""Validation utilities for varieties, reviews, and uploads."""

from __future__ import annotations

from datetime import date, datetime

from src.constants.prefectures import PREFECTURES
from src.utils.text_utils import normalize_text


def validate_year(value: int | None) -> int | None:
    """Validate year in conservative allowed range."""
    if value is None:
        return None
    current_year = date.today().year + 1
    if value < 1900 or value > current_year:
        raise ValueError("年の範囲が不正です。")
    return value


def validate_month(value: int | None) -> int | None:
    """Validate month range."""
    if value is None:
        return None
    if value < 1 or value > 12:
        raise ValueError("月の範囲が不正です。")
    return value


def validate_prefecture(value: str | None) -> str | None:
    """Validate optional prefecture."""
    if value is None or value == "":
        return None
    if value not in PREFECTURES:
        raise ValueError("都道府県が不正です。")
    return value


def validate_variety_payload(payload: dict) -> dict:
    """Validate variety payload."""
    payload["name"] = normalize_text(payload.get("name", ""))
    if not (1 <= len(payload["name"]) <= 100):
        raise ValueError("品種名は1〜100文字で入力してください。")
    payload["developer"] = normalize_text(payload.get("developer", ""))
    if len(payload["developer"]) > 200:
        raise ValueError("開発者名は200文字以内です。")
    payload["description"] = normalize_text(payload.get("description", ""))
    if len(payload["description"]) > 5000:
        raise ValueError("説明は5000文字以内です。")
    payload["origin_prefecture"] = validate_prefecture(payload.get("origin_prefecture"))
    payload["registered_year"] = validate_year(payload.get("registered_year"))
    payload["harvest_start_month"] = validate_month(payload.get("harvest_start_month"))
    payload["harvest_end_month"] = validate_month(payload.get("harvest_end_month"))
    brix_min = payload.get("brix_min")
    brix_max = payload.get("brix_max")
    if brix_min is not None and not (0 <= float(brix_min) <= 30):
        raise ValueError("糖度下限は0〜30です。")
    if brix_max is not None and not (0 <= float(brix_max) <= 30):
        raise ValueError("糖度上限は0〜30です。")
    if brix_min is not None and brix_max is not None and float(brix_min) > float(brix_max):
        raise ValueError("糖度下限は上限以下にしてください。")
    return payload


def normalize_review_tasted_date(value: date | str) -> str:
    """Normalize review tasted_date to ISO date string after validation."""
    parsed_date: date
    if isinstance(value, datetime):
        parsed_date = value.date()
    elif isinstance(value, date):
        parsed_date = value
    elif isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            raise ValueError("試食日は必須です。")
        try:
            parsed_date = date.fromisoformat(normalized)
        except ValueError as exc:
            raise ValueError("試食日の形式が不正です。") from exc
    else:
        raise ValueError("試食日の形式が不正です。")
    if parsed_date > date.today():
        raise ValueError("試食日は今日以前のみです。")
    return parsed_date.isoformat()


def validate_review_payload(payload: dict) -> dict:
    """Validate review payload."""
    payload["tasted_date"] = normalize_review_tasted_date(payload["tasted_date"])
    for key in ("sweetness", "sourness", "aroma", "texture", "appearance"):
        if int(payload[key]) not in (1, 2, 3, 4, 5):
            raise ValueError(f"{key} は1〜5です。")
    if not (1 <= int(payload["overall"]) <= 10):
        raise ValueError("総合評価は1〜10です。")
    payload["purchase_place"] = normalize_text(payload.get("purchase_place", ""))
    if len(payload["purchase_place"]) > 200:
        raise ValueError("購入場所は200文字以内です。")
    price = payload.get("price_jpy")
    if price is not None and not (0 <= int(price) <= 1_000_000):
        raise ValueError("価格は0〜1000000円です。")
    payload["comment"] = normalize_text(payload.get("comment", ""))
    if len(payload["comment"]) > 5000:
        raise ValueError("コメントは5000文字以内です。")
    return payload


