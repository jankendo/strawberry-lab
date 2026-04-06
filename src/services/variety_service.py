"""Variety CRUD and pedigree link operations."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime
from uuid import uuid4

import networkx as nx
import streamlit as st

from src.services.auth_service import get_user_client
from src.utils.validation import validate_variety_payload


def _apply_variety_filters(
    query,
    *,
    include_deleted: bool,
    keyword: str | None,
    prefecture: str | None,
    tags: Sequence[str] | None,
):
    if not include_deleted:
        query = query.is_("deleted_at", "null")
    if keyword:
        query = query.or_(
            "name.ilike.%{kw}%,registration_number.ilike.%{kw}%,application_number.ilike.%{kw}%"
            ",developer.ilike.%{kw}%,description.ilike.%{kw}%".format(kw=keyword)
        )
    if prefecture:
        query = query.eq("origin_prefecture", prefecture)
    if tags:
        query = query.contains("tags", list(tags))
    return query


@st.cache_data(ttl=300)
def list_varieties(
    *,
    include_deleted: bool = False,
    keyword: str | None = None,
    prefecture: str | None = None,
    tags: Sequence[str] | None = None,
    sort_field: str = "updated_at",
    sort_desc: bool = True,
    page: int = 1,
    page_size: int = 20,
    fields: str = "*",
) -> tuple[list[dict], int]:
    """List varieties with filters and pagination."""
    client = get_user_client()
    query = _apply_variety_filters(
        client.table("varieties").select(fields),
        include_deleted=include_deleted,
        keyword=keyword,
        prefecture=prefecture,
        tags=tags,
    )
    allowed_sort = {"name", "updated_at", "registered_year", "created_at", "registration_date"}
    if sort_field not in allowed_sort:
        sort_field = "updated_at"
    result = query.order(sort_field, desc=sort_desc).range((page - 1) * page_size, page * page_size - 1).execute()
    count_query = _apply_variety_filters(
        client.table("varieties").select("id", count="exact", head=True),
        include_deleted=include_deleted,
        keyword=keyword,
        prefecture=prefecture,
        tags=tags,
    )
    count_result = count_query.execute()
    total = int(count_result.count or 0)
    return result.data or [], total


@st.cache_data(ttl=120)
def get_variety_detail(variety_id: str) -> dict | None:
    """Fetch single variety detail."""
    client = get_user_client()
    result = client.table("varieties").select("*").eq("id", variety_id).maybe_single().execute()
    return result.data


@st.cache_data(ttl=300)
def list_active_varieties() -> list[dict]:
    """List active varieties for selectors."""
    client = get_user_client()
    result = client.table("varieties").select("id,name,alias_names").is_("deleted_at", "null").order("name").execute()
    return result.data or []


@st.cache_data(ttl=180)
def get_review_counts_for_varieties(variety_ids: Sequence[str]) -> dict[str, int]:
    """Return review counts keyed by variety ID for the given IDs."""
    ids = [v for v in dict.fromkeys(variety_ids) if v]
    if not ids:
        return {}
    client = get_user_client()
    rows = (
        client.table("reviews")
        .select("variety_id")
        .in_("variety_id", ids)
        .is_("deleted_at", "null")
        .execute()
        .data
        or []
    )
    counts: dict[str, int] = {variety_id: 0 for variety_id in ids}
    for row in rows:
        variety_id = row.get("variety_id")
        if variety_id in counts:
            counts[variety_id] += 1
    return counts


@st.cache_data(ttl=180)
def get_pokedex_progress() -> dict[str, int]:
    """Return encyclopedia progress counts based on review registration."""
    client = get_user_client()
    total_varieties = (
        client.table("varieties")
        .select("id", count="exact", head=True)
        .is_("deleted_at", "null")
        .execute()
        .count
        or 0
    )
    reviewed_rows = client.table("reviews").select("variety_id").is_("deleted_at", "null").execute().data or []
    discovered_ids = {row.get("variety_id") for row in reviewed_rows if row.get("variety_id")}
    discovered_count = len(discovered_ids)
    completion_rate = int((discovered_count / total_varieties) * 100) if total_varieties else 0
    return {
        "total_varieties": int(total_varieties),
        "discovered_count": discovered_count,
        "undiscovered_count": max(0, int(total_varieties) - discovered_count),
        "completion_rate": completion_rate,
    }


def create_variety(payload: dict, parent_links: list[dict]) -> str:
    """Create a new variety and optional parent links."""
    client = get_user_client()
    payload = validate_variety_payload(payload)
    payload["id"] = str(uuid4())
    insert_result = client.table("varieties").insert(payload).execute()
    variety_id = insert_result.data[0]["id"]
    if parent_links:
        upsert_parent_links(variety_id, parent_links)
    list_varieties.clear()
    get_variety_detail.clear()
    get_pokedex_progress.clear()
    get_review_counts_for_varieties.clear()
    return variety_id


def update_variety(variety_id: str, payload: dict, parent_links: list[dict]) -> None:
    """Update variety and replace parent links."""
    client = get_user_client()
    payload = validate_variety_payload(payload)
    client.table("varieties").update(payload).eq("id", variety_id).execute()
    client.table("variety_parent_links").delete().eq("child_variety_id", variety_id).execute()
    if parent_links:
        upsert_parent_links(variety_id, parent_links)
    list_varieties.clear()
    get_variety_detail.clear()
    get_pokedex_progress.clear()
    get_review_counts_for_varieties.clear()


def soft_delete_variety(variety_id: str) -> None:
    """Soft delete variety."""
    client = get_user_client()
    client.table("varieties").update({"deleted_at": datetime.now(tz=UTC).isoformat()}).eq("id", variety_id).execute()
    list_varieties.clear()
    get_variety_detail.clear()
    get_pokedex_progress.clear()
    get_review_counts_for_varieties.clear()


def restore_variety(variety_id: str) -> None:
    """Restore soft-deleted variety."""
    client = get_user_client()
    row = client.table("varieties").select("id,name").eq("id", variety_id).single().execute().data
    duplicate = (
        client.table("varieties")
        .select("id")
        .neq("id", variety_id)
        .is_("deleted_at", "null")
        .ilike("name", row["name"])
        .execute()
    )
    if duplicate.data:
        raise ValueError("同名の有効な品種が存在するため復元できません。")
    client.table("varieties").update({"deleted_at": None}).eq("id", variety_id).execute()
    list_varieties.clear()
    get_variety_detail.clear()
    get_pokedex_progress.clear()
    get_review_counts_for_varieties.clear()


def upsert_parent_links(child_variety_id: str, parent_links: list[dict]) -> None:
    """Create parent links after DAG check."""
    for link in parent_links:
        parent_id = link["parent_variety_id"]
        if would_create_cycle(parent_id, child_variety_id):
            raise ValueError("交配リンクで循環が発生します。")
    client = get_user_client()
    rows = [
        {
            "id": str(uuid4()),
            "child_variety_id": child_variety_id,
            "parent_variety_id": link["parent_variety_id"],
            "parent_order": link.get("parent_order"),
            "crossed_year": link.get("crossed_year"),
            "note": link.get("note", ""),
        }
        for link in parent_links
    ]
    client.table("variety_parent_links").insert(rows).execute()


def would_create_cycle(parent_variety_id: str, child_variety_id: str) -> bool:
    """Check cycle creation using current links and a tentative edge."""
    if parent_variety_id == child_variety_id:
        return True
    client = get_user_client()
    links = client.table("variety_parent_links").select("parent_variety_id,child_variety_id").execute().data or []
    graph = nx.DiGraph()
    for link in links:
        graph.add_edge(link["parent_variety_id"], link["child_variety_id"])
    graph.add_edge(parent_variety_id, child_variety_id)
    return not nx.is_directed_acyclic_graph(graph)


def get_variety_stats(variety_id: str) -> dict:
    """Fetch linked reviews and notes counts."""
    client = get_user_client()
    review_count = (
        client.table("reviews").select("id", count="exact", head=True).eq("variety_id", variety_id).is_("deleted_at", "null").execute()
    )
    note_count = (
        client.table("notes").select("id", count="exact", head=True).eq("variety_id", variety_id).is_("deleted_at", "null").execute()
    )
    return {"review_count": int(review_count.count or 0), "note_count": int(note_count.count or 0), "as_of": date.today().isoformat()}
