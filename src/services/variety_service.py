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
from src.utils.text_utils import build_search_key, normalize_search_text
from src.utils.validation import validate_variety_payload

LIST_TAB_FIELDS = (
    "id,name,alias_names,japanese_name,origin_prefecture,registration_number,application_number,"
    "description,characteristics_summary,developer,updated_at,created_at,registered_year,registration_date"
)
LIST_TAB_SORT_FIELDS = "id,name,origin_prefecture,updated_at,created_at,registered_year,registration_date"
_POSTGREST_IN_CHUNK_SIZE = 200
_LIST_TAB_INDEX_BATCH_SIZE = 1000


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


def _build_variety_search_key(row: dict) -> str:
    return build_search_key(
        [
            row.get("name"),
            row.get("alias_names") or [],
            row.get("japanese_name"),
            row.get("registration_number"),
            row.get("application_number"),
            row.get("developer"),
            row.get("description"),
            row.get("characteristics_summary"),
        ]
    )


def _coerce_variety_sort_value(value: object) -> object:
    if value in {None, ""}:
        return ""
    if isinstance(value, (int, float)):
        return value
    return normalize_search_text(str(value))


def _annotate_variety_index_rows(rows: Sequence[dict]) -> list[dict]:
    return [{**row, "_search_key": _build_variety_search_key(row)} for row in rows]


def _sort_variety_rows(rows: Sequence[dict], *, sort_field: str, sort_desc: bool) -> list[dict]:
    sorted_rows = [dict(row) for row in rows]
    sorted_rows.sort(key=lambda row: _coerce_variety_sort_value(row.get(sort_field)), reverse=sort_desc)
    sorted_rows.sort(key=lambda row: row.get(sort_field) in {None, ""})
    return sorted_rows


def _ordered_variety_rows_by_ids(rows: Sequence[dict], ordered_ids: Sequence[str]) -> list[dict]:
    row_by_id = {str(row.get("id") or ""): dict(row) for row in rows if row.get("id")}
    return [row_by_id[variety_id] for variety_id in ordered_ids if variety_id in row_by_id]


def _row_matches_variety_list_filters(
    row: dict,
    *,
    normalized_keyword: str,
    prefecture: str | None,
    discovery_filter: str,
    discovered_id_set: set[str],
) -> bool:
    row_id = str(row.get("id") or "").strip()
    if not row_id:
        return False
    if normalized_keyword and normalized_keyword not in str(row.get("_search_key") or _build_variety_search_key(row)):
        return False
    if prefecture and str(row.get("origin_prefecture") or "") != prefecture:
        return False
    if discovery_filter == "発見済み" and row_id not in discovered_id_set:
        return False
    if discovery_filter == "未発見" and row_id in discovered_id_set:
        return False
    return True


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
def list_variety_list_index() -> list[dict]:
    """Return a cached lightweight index for the varieties list tab."""
    client = get_user_client()
    rows: list[dict] = []
    start = 0
    seen_batch_ids: set[tuple[str, ...]] = set()
    while True:
        chunk = (
            client.table("varieties")
            .select(LIST_TAB_FIELDS)
            .is_("deleted_at", "null")
            .order("id")
            .range(start, start + _LIST_TAB_INDEX_BATCH_SIZE - 1)
            .execute()
            .data
            or []
        )
        if not chunk:
            break
        batch_ids = tuple(str(row.get("id") or "") for row in chunk if row.get("id"))
        if batch_ids and batch_ids in seen_batch_ids:
            break
        if batch_ids:
            seen_batch_ids.add(batch_ids)
        rows.extend(_annotate_variety_index_rows(chunk))
        if len(chunk) < _LIST_TAB_INDEX_BATCH_SIZE:
            break
        start += len(chunk)
    return rows


@scoped_cache_data(ttl=900, scopes="varieties")
def list_variety_sort_index() -> list[dict]:
    """Return a cached lightweight sort/filter index for the varieties list tab."""
    client = get_user_client()
    rows: list[dict] = []
    start = 0
    seen_batch_ids: set[tuple[str, ...]] = set()
    while True:
        chunk = (
            client.table("varieties")
            .select(LIST_TAB_SORT_FIELDS)
            .is_("deleted_at", "null")
            .order("id")
            .range(start, start + _LIST_TAB_INDEX_BATCH_SIZE - 1)
            .execute()
            .data
            or []
        )
        if not chunk:
            break
        batch_ids = tuple(str(row.get("id") or "") for row in chunk if row.get("id"))
        if batch_ids and batch_ids in seen_batch_ids:
            break
        if batch_ids:
            seen_batch_ids.add(batch_ids)
        rows.extend(dict(row) for row in chunk)
        if len(chunk) < _LIST_TAB_INDEX_BATCH_SIZE:
            break
        start += len(chunk)
    return rows


@scoped_cache_data(ttl=180, scopes=("varieties", "reviews"))
def get_discovered_variety_ids() -> list[str]:
    """Return IDs of varieties that have at least one active review."""
    client = get_user_client()
    discovered_ids: list[str] = []
    seen_variety_ids: set[str] = set()
    seen_batch_review_ids: set[tuple[str, ...]] = set()
    start = 0
    while True:
        reviewed_rows = (
            client.table("reviews")
            .select("id,variety_id")
            .is_("deleted_at", "null")
            .order("id")
            .range(start, start + _LIST_TAB_INDEX_BATCH_SIZE - 1)
            .execute()
            .data
            or []
        )
        if not reviewed_rows:
            break
        batch_review_ids = tuple(str(row.get("id") or "") for row in reviewed_rows if row.get("id"))
        if batch_review_ids and batch_review_ids in seen_batch_review_ids:
            break
        if batch_review_ids:
            seen_batch_review_ids.add(batch_review_ids)
        for row in reviewed_rows:
            variety_id = str(row.get("variety_id") or "").strip()
            if variety_id and variety_id not in seen_variety_ids:
                seen_variety_ids.add(variety_id)
                discovered_ids.append(variety_id)
        if len(reviewed_rows) < _LIST_TAB_INDEX_BATCH_SIZE:
            break
        start += len(reviewed_rows)
    return discovered_ids


@scoped_cache_data(ttl=900, scopes=("varieties", "reviews"))
def list_variety_list_index_for_ids(variety_ids: Sequence[str]) -> list[dict]:
    """Return a cached lightweight index for a specific variety ID set."""
    ids = [str(variety_id) for variety_id in dict.fromkeys(variety_ids) if str(variety_id).strip()]
    if not ids:
        return []
    client = get_user_client()
    rows: list[dict] = []
    for id_chunk in chunked_sequence(ids, _POSTGREST_IN_CHUNK_SIZE):
        chunk = (
            client.table("varieties")
            .select(LIST_TAB_FIELDS)
            .in_("id", id_chunk)
            .is_("deleted_at", "null")
            .execute()
            .data
            or []
        )
        rows.extend(chunk)
    rows.sort(key=lambda row: normalize_search_text(str(row.get("id") or "")))
    return _annotate_variety_index_rows(rows)


@scoped_cache_data(ttl=900, scopes="varieties")
def list_variety_sort_index_for_ids(variety_ids: Sequence[str]) -> list[dict]:
    """Return a cached lightweight sort/filter index for a specific variety ID set."""
    ids = [str(variety_id) for variety_id in dict.fromkeys(variety_ids) if str(variety_id).strip()]
    if not ids:
        return []
    client = get_user_client()
    rows: list[dict] = []
    for id_chunk in chunked_sequence(ids, _POSTGREST_IN_CHUNK_SIZE):
        chunk = (
            client.table("varieties")
            .select(LIST_TAB_SORT_FIELDS)
            .in_("id", id_chunk)
            .is_("deleted_at", "null")
            .execute()
            .data
            or []
        )
        rows.extend(dict(row) for row in chunk)
    rows.sort(key=lambda row: normalize_search_text(str(row.get("id") or "")))
    return rows


def get_variety_list_page_ids(
    *,
    keyword: str | None = None,
    prefecture: str | None = None,
    discovery_filter: str = "すべて",
    sort_field: str = "updated_at",
    sort_desc: bool = True,
    page: int = 1,
    page_size: int = 50,
    selected_id: str | None = None,
) -> tuple[list[str], int, bool]:
    """Return ordered page IDs, total matches, and whether the selected row still matches filters."""
    allowed_sort = {"name", "updated_at", "registered_year", "created_at", "registration_date"}
    if sort_field not in allowed_sort:
        sort_field = "updated_at"
    normalized_keyword = normalize_search_text(keyword or "")
    normalized_selected_id = str(selected_id or "").strip()
    normalized_page = max(int(page), 1)
    normalized_page_size = max(int(page_size), 1)
    discovered_ids: list[str] = []
    discovered_id_set: set[str] = set()
    if discovery_filter in {"発見済み", "未発見"}:
        discovered_ids = get_discovered_variety_ids()
        discovered_id_set = set(discovered_ids)
    if not normalized_keyword and discovery_filter == "すべて" and not prefecture:
        page_rows, total = list_varieties(
            include_deleted=False,
            sort_field=sort_field,
            sort_desc=sort_desc,
            page=normalized_page,
            page_size=normalized_page_size,
            fields="id",
        )
        page_ids = [str(row.get("id") or "") for row in page_rows if row.get("id")]
        if not normalized_selected_id:
            return page_ids, total, True
        selected_rows = list_variety_sort_index_for_ids([normalized_selected_id])
        return page_ids, total, bool(selected_rows)
    if normalized_keyword:
        source_rows = (
            [dict(row) for row in list_variety_list_index_for_ids(discovered_ids)]
            if discovery_filter == "発見済み"
            else [dict(row) for row in list_variety_list_index()]
        )
    else:
        source_rows = (
            [dict(row) for row in list_variety_sort_index_for_ids(discovered_ids)]
            if discovery_filter == "発見済み"
            else [dict(row) for row in list_variety_sort_index()]
        )
    filtered_rows = [
        row
        for row in source_rows
        if _row_matches_variety_list_filters(
            row,
            normalized_keyword=normalized_keyword,
            prefecture=prefecture or None,
            discovery_filter=discovery_filter,
            discovered_id_set=discovered_id_set,
        )
    ]
    ordered_rows = _sort_variety_rows(filtered_rows, sort_field=sort_field, sort_desc=sort_desc)
    total = len(ordered_rows)
    page_start = (normalized_page - 1) * normalized_page_size
    page_ids = [str(row.get("id") or "") for row in ordered_rows[page_start : page_start + normalized_page_size] if row.get("id")]
    if not normalized_selected_id:
        return page_ids, total, True
    if any(str(row.get("id") or "") == normalized_selected_id for row in ordered_rows):
        return page_ids, total, True
    selected_rows = list_variety_list_index_for_ids([normalized_selected_id]) if normalized_keyword else list_variety_sort_index_for_ids([normalized_selected_id])
    if not selected_rows:
        return page_ids, total, False
    return (
        page_ids,
        total,
        _row_matches_variety_list_filters(
            dict(selected_rows[0]),
            normalized_keyword=normalized_keyword,
            prefecture=prefecture or None,
            discovery_filter=discovery_filter,
            discovered_id_set=discovered_id_set,
        ),
    )


def get_variety_list_rows(variety_ids: Sequence[str]) -> list[dict]:
    """Return ordered list-tab rows for the provided page IDs."""
    ids = [str(variety_id) for variety_id in variety_ids if str(variety_id).strip()]
    if not ids:
        return []
    return _ordered_variety_rows_by_ids(list_variety_list_index_for_ids(ids), ids)


def list_varieties_for_list_tab(
    *,
    keyword: str | None = None,
    prefecture: str | None = None,
    discovery_filter: str = "すべて",
    sort_field: str = "updated_at",
    sort_desc: bool = True,
    page: int = 1,
    page_size: int = 50,
    selected_id: str | None = None,
) -> tuple[list[dict], int, bool]:
    """List active varieties for the list tab using cached local filtering."""
    page_ids, total, selected_matches = get_variety_list_page_ids(
        keyword=keyword,
        prefecture=prefecture,
        discovery_filter=discovery_filter,
        sort_field=sort_field,
        sort_desc=sort_desc,
        page=page,
        page_size=page_size,
        selected_id=selected_id,
    )
    return get_variety_list_rows(page_ids), total, selected_matches


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
    discovered_ids = set(get_discovered_variety_ids())
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
    list_variety_list_index.clear()
    list_variety_sort_index.clear()
    list_variety_list_index_for_ids.clear()
    list_variety_sort_index_for_ids.clear()
    list_active_varieties.clear()
    get_variety_detail.clear()
    get_discovered_variety_ids.clear()
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
