"""Notes CRUD and search service."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import streamlit as st

from src.services.auth_service import get_user_client
from src.utils.validation import validate_note_payload


@st.cache_data(ttl=300)
def list_notes(
    *,
    include_deleted: bool = False,
    search_query: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int]:
    """List notes, using DB-side search RPC when query provided."""
    client = get_user_client()
    if search_query:
        rpc = client.rpc("search_notes", {"search_query": search_query}).execute()
        rows = rpc.data or []
        if not include_deleted:
            rows = [row for row in rows if row.get("deleted_at") is None]
        total = len(rows)
        start = (page - 1) * page_size
        return rows[start : start + page_size], total
    query = client.table("notes").select("*")
    if not include_deleted:
        query = query.is_("deleted_at", "null")
    rows = query.order("updated_at", desc=True).range((page - 1) * page_size, page * page_size - 1).execute().data or []
    count_query = client.table("notes").select("id", count="exact", head=True)
    if not include_deleted:
        count_query = count_query.is_("deleted_at", "null")
    total = int(count_query.execute().count or 0)
    return rows, total


def create_note(payload: dict) -> str:
    """Create note."""
    client = get_user_client()
    payload = validate_note_payload(payload)
    payload["id"] = str(uuid4())
    result = client.table("notes").insert(payload).execute()
    list_notes.clear()
    return result.data[0]["id"]


def update_note(note_id: str, payload: dict) -> None:
    """Update note."""
    client = get_user_client()
    payload = validate_note_payload(payload)
    client.table("notes").update(payload).eq("id", note_id).execute()
    list_notes.clear()


def soft_delete_note(note_id: str) -> None:
    """Soft delete note."""
    client = get_user_client()
    client.table("notes").update({"deleted_at": datetime.now(tz=UTC).isoformat()}).eq("id", note_id).execute()
    list_notes.clear()


def restore_note(note_id: str) -> None:
    """Restore note."""
    client = get_user_client()
    client.table("notes").update({"deleted_at": None}).eq("id", note_id).execute()
    list_notes.clear()
