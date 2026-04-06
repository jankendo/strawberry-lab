"""Review CRUD and duplicate control."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import streamlit as st

from src.services.auth_service import get_user_client
from src.services.export_service import clear_export_cache
from src.services.variety_service import get_pokedex_progress, get_review_counts_for_varieties
from src.utils.validation import validate_review_payload


def _response_data(response):
    if response is None:
        return None
    return getattr(response, "data", None)


@st.cache_data(ttl=300)
def list_reviews(
    *,
    include_deleted: bool = False,
    variety_id: str | None = None,
    date_from=None,
    date_to=None,
    overall_min: int | None = None,
    overall_max: int | None = None,
    sort_field: str = "tasted_date",
    sort_desc: bool = True,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int]:
    """List reviews with filters and pagination."""
    client = get_user_client()
    query = client.table("reviews").select("*, varieties(name)")
    if not include_deleted:
        query = query.is_("deleted_at", "null")
    if variety_id:
        query = query.eq("variety_id", variety_id)
    if date_from:
        query = query.gte("tasted_date", str(date_from))
    if date_to:
        query = query.lte("tasted_date", str(date_to))
    if overall_min is not None:
        query = query.gte("overall", overall_min)
    if overall_max is not None:
        query = query.lte("overall", overall_max)
    allowed_sort = {"tasted_date", "updated_at", "overall"}
    if sort_field not in allowed_sort:
        sort_field = "tasted_date"
    data = query.order(sort_field, desc=sort_desc).range((page - 1) * page_size, page * page_size - 1).execute().data or []
    count_query = client.table("reviews").select("id", count="exact", head=True)
    if not include_deleted:
        count_query = count_query.is_("deleted_at", "null")
    if variety_id:
        count_query = count_query.eq("variety_id", variety_id)
    if date_from:
        count_query = count_query.gte("tasted_date", str(date_from))
    if date_to:
        count_query = count_query.lte("tasted_date", str(date_to))
    if overall_min is not None:
        count_query = count_query.gte("overall", overall_min)
    if overall_max is not None:
        count_query = count_query.lte("overall", overall_max)
    total = int(count_query.execute().count or 0)
    return data, total


def _find_duplicate(variety_id: str, tasted_date: str) -> dict | None:
    client = get_user_client()
    result = (
        client.table("reviews")
        .select("id")
        .eq("variety_id", variety_id)
        .eq("tasted_date", tasted_date)
        .is_("deleted_at", "null")
        .maybe_single()
        .execute()
    )
    data = _response_data(result)
    if isinstance(data, list):
        return data[0] if data else None
    return data if isinstance(data, dict) else None


def create_or_update_review(payload: dict, *, overwrite_duplicate: bool = False) -> tuple[str, bool]:
    """Create review; optionally overwrite duplicate by variety/date."""
    client = get_user_client()
    payload = validate_review_payload(payload)
    duplicate = _find_duplicate(payload["variety_id"], payload["tasted_date"])
    if duplicate and not overwrite_duplicate:
        raise ValueError("DUPLICATE_REVIEW")
    if duplicate:
        review_id = duplicate["id"]
        client.table("reviews").update(payload).eq("id", review_id).execute()
        list_reviews.clear()
        get_pokedex_progress.clear()
        get_review_counts_for_varieties.clear()
        clear_export_cache()
        return review_id, True
    review_id = str(uuid4())
    payload["id"] = review_id
    client.table("reviews").insert(payload).execute()
    list_reviews.clear()
    get_pokedex_progress.clear()
    get_review_counts_for_varieties.clear()
    clear_export_cache()
    return review_id, False


def update_review(review_id: str, payload: dict) -> None:
    """Update a review row."""
    client = get_user_client()
    payload = validate_review_payload(payload)
    client.table("reviews").update(payload).eq("id", review_id).execute()
    list_reviews.clear()
    get_pokedex_progress.clear()
    get_review_counts_for_varieties.clear()
    clear_export_cache()


def soft_delete_review(review_id: str) -> None:
    """Soft delete review."""
    client = get_user_client()
    client.table("reviews").update({"deleted_at": datetime.now(tz=UTC).isoformat()}).eq("id", review_id).execute()
    list_reviews.clear()
    get_pokedex_progress.clear()
    get_review_counts_for_varieties.clear()
    clear_export_cache()


def restore_review(review_id: str) -> None:
    """Restore review if duplicate active key does not exist."""
    client = get_user_client()
    row = client.table("reviews").select("id,variety_id,tasted_date").eq("id", review_id).single().execute().data
    conflict = (
        client.table("reviews")
        .select("id")
        .neq("id", review_id)
        .eq("variety_id", row["variety_id"])
        .eq("tasted_date", row["tasted_date"])
        .is_("deleted_at", "null")
        .execute()
    )
    if conflict.data:
        raise ValueError("同じ品種・日付の有効レビューが存在するため復元できません。")
    client.table("reviews").update({"deleted_at": None}).eq("id", review_id).execute()
    list_reviews.clear()
    get_pokedex_progress.clear()
    get_review_counts_for_varieties.clear()
    clear_export_cache()
