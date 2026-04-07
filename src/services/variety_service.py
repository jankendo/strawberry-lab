"""Variety CRUD and pedigree link operations."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime
from uuid import uuid4

import networkx as nx

from src.services.auth_service import get_user_client
from src.services.cache_service import bump_cache_scopes, scoped_cache_data
from src.services.export_service import clear_export_cache
from src.services.pedigree_service import clear_pedigree_cache
from src.utils.batching import chunked_sequence
from src.utils.validation import validate_variety_payload

LIST_TAB_FIELDS = "id,name,origin_prefecture,registration_number,application_number,description,characteristics_summary"
_POSTGREST_IN_CHUNK_SIZE = 200


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


@scoped_cache_data(ttl=300, scopes="varieties")
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


@scoped_cache_data(ttl=900, scopes="varieties")
def list_varieties_for_list_tab(
    *,
    keyword: str | None = None,
    prefecture: str | None = None,
    sort_field: str = "updated_at",
    sort_desc: bool = True,
) -> tuple[list[dict], int]:
    """List all active varieties for list tab filtering."""
    client = get_user_client()
    allowed_sort = {"name", "updated_at", "registered_year", "created_at", "registration_date"}
    if sort_field not in allowed_sort:
        sort_field = "updated_at"

    batch_size = 500
    rows: list[dict] = []
    start = 0
    while True:
        query = _apply_variety_filters(
            client.table("varieties").select(LIST_TAB_FIELDS),
            include_deleted=False,
            keyword=keyword,
            prefecture=prefecture,
            tags=None,
        )
        chunk = query.order(sort_field, desc=sort_desc).range(start, start + batch_size - 1).execute().data or []
        rows.extend(chunk)
        if len(chunk) < batch_size:
            break
        start += batch_size
    return rows, len(rows)


@scoped_cache_data(ttl=120, scopes="varieties")
def get_variety_detail(variety_id: str) -> dict | None:
    """Fetch single variety detail."""
    client = get_user_client()
    result = client.table("varieties").select("*").eq("id", variety_id).maybe_single().execute()
    return result.data


@scoped_cache_data(ttl=300, scopes="varieties")
def list_active_varieties() -> list[dict]:
    """List active varieties for selectors."""
    client = get_user_client()
    result = client.table("varieties").select("id,name,alias_names").is_("deleted_at", "null").order("name").execute()
    return result.data or []


@scoped_cache_data(ttl=180, scopes=("varieties", "reviews"))
def get_review_counts_for_varieties(variety_ids: Sequence[str]) -> dict[str, int]:
    """Return review counts keyed by variety ID for the given IDs."""
    ids = [v for v in dict.fromkeys(variety_ids) if v]
    if not ids:
        return {}
    client = get_user_client()
    counts: dict[str, int] = {variety_id: 0 for variety_id in ids}
    for id_chunk in chunked_sequence(ids, _POSTGREST_IN_CHUNK_SIZE):
        rows = (
            client.table("reviews")
            .select("variety_id")
            .in_("variety_id", id_chunk)
            .is_("deleted_at", "null")
            .execute()
            .data
            or []
        )
        for row in rows:
            variety_id = row.get("variety_id")
            if variety_id in counts:
                counts[variety_id] += 1
    return counts


@scoped_cache_data(ttl=180, scopes=("varieties", "reviews"))
def get_latest_review_summary_for_varieties(variety_ids: Sequence[str]) -> dict[str, dict]:
    """Return latest review metrics keyed by variety ID."""
    ids = [str(variety_id) for variety_id in dict.fromkeys(variety_ids) if variety_id]
    if not ids:
        return {}
    client = get_user_client()
    latest_by_variety: dict[str, dict] = {}
    for id_chunk in chunked_sequence(ids, _POSTGREST_IN_CHUNK_SIZE):
        rows = (
            client.table("reviews")
            .select("variety_id,tasted_date,overall,sweetness,sourness,aroma,texture,appearance,updated_at,created_at")
            .in_("variety_id", id_chunk)
            .is_("deleted_at", "null")
            .order("tasted_date", desc=True)
            .order("updated_at", desc=True)
            .order("created_at", desc=True)
            .execute()
            .data
            or []
        )
        for row in rows:
            variety_id = str(row.get("variety_id") or "")
            if variety_id and variety_id not in latest_by_variety:
                latest_by_variety[variety_id] = row
    return latest_by_variety


@scoped_cache_data(ttl=180, scopes=("varieties", "reviews"))
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


def _clear_variety_related_caches() -> None:
    list_varieties.clear()
    list_varieties_for_list_tab.clear()
    list_active_varieties.clear()
    get_variety_detail.clear()
    get_pokedex_progress.clear()
    get_review_counts_for_varieties.clear()
    get_latest_review_summary_for_varieties.clear()
    clear_pedigree_cache()
    clear_export_cache()
    bump_cache_scopes("varieties", "pedigree", "exports", "analytics")


def create_variety(payload: dict, parent_links: list[dict]) -> str:
    """Create a new variety and optional parent links."""
    client = get_user_client()
    payload = validate_variety_payload(payload)
    payload["id"] = str(uuid4())
    insert_result = client.table("varieties").insert(payload).execute()
    variety_id = insert_result.data[0]["id"]
    if parent_links:
        upsert_parent_links(variety_id, parent_links)
    _clear_variety_related_caches()
    return variety_id


def update_variety(variety_id: str, payload: dict, parent_links: list[dict]) -> None:
    """Update variety and replace parent links."""
    client = get_user_client()
    payload = validate_variety_payload(payload)
    client.table("varieties").update(payload).eq("id", variety_id).execute()
    client.table("variety_parent_links").delete().eq("child_variety_id", variety_id).execute()
    if parent_links:
        upsert_parent_links(variety_id, parent_links)
    _clear_variety_related_caches()


def soft_delete_variety(variety_id: str) -> None:
    """Soft delete variety."""
    client = get_user_client()
    client.table("varieties").update({"deleted_at": datetime.now(tz=UTC).isoformat()}).eq("id", variety_id).execute()
    _clear_variety_related_caches()


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
    _clear_variety_related_caches()


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
    clear_export_cache()


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
    """Fetch linked review counts."""
    client = get_user_client()
    review_count = (
        client.table("reviews").select("id", count="exact", head=True).eq("variety_id", variety_id).is_("deleted_at", "null").execute()
    )
    return {"review_count": int(review_count.count or 0), "as_of": date.today().isoformat()}
