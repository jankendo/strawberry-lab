"""Supabase Storage image management service."""

from __future__ import annotations

from collections.abc import Sequence
import mimetypes
from pathlib import Path
from uuid import uuid4

import streamlit as st

from src.services.auth_service import get_user_client
from src.utils.image_utils import process_image, validate_image_file


def _safe_file_stem(name: str) -> str:
    stem = Path(name).stem.lower()
    safe = "".join(ch if ch.isalnum() or ch in ("_", "-") else "_" for ch in stem).strip("_")
    return safe[:80] or "image"


def _upload_image(
    *,
    bucket: str,
    base_path: str,
    relation_column: str,
    relation_id: str,
    file_name: str,
    raw_bytes: bytes,
) -> dict:
    client = get_user_client()
    mime_type = mimetypes.guess_type(file_name)[0] or "application/octet-stream"
    validate_image_file(file_name, mime_type, raw_bytes)
    ext = Path(file_name).suffix.lower()
    processed = process_image(raw_bytes, ext)
    storage_path = f"{base_path}/{relation_id}/{uuid4()}_{_safe_file_stem(file_name)}{processed.extension}"
    client.storage.from_(bucket).upload(
        path=storage_path,
        file=processed.bytes_data,
        file_options={"content-type": processed.mime_type, "upsert": "false"},
    )
    metadata = {
        "id": str(uuid4()),
        relation_column: relation_id,
        "storage_path": storage_path,
        "file_name": file_name,
        "mime_type": processed.mime_type,
        "file_size_bytes": processed.file_size_bytes,
        "width": processed.width,
        "height": processed.height,
    }
    table = "variety_images" if relation_column == "variety_id" else "review_images"
    inserted = client.table(table).insert(metadata).execute().data[0]
    _clear_image_cache()
    return inserted


def upload_variety_image(variety_id: str, file_name: str, raw_bytes: bytes) -> dict:
    """Validate/process/upload image for a variety."""
    return _upload_image(
        bucket="variety-images",
        base_path="varieties",
        relation_column="variety_id",
        relation_id=variety_id,
        file_name=file_name,
        raw_bytes=raw_bytes,
    )


def upload_review_image(review_id: str, file_name: str, raw_bytes: bytes) -> dict:
    """Validate/process/upload image for a review."""
    return _upload_image(
        bucket="review-images",
        base_path="reviews",
        relation_column="review_id",
        relation_id=review_id,
        file_name=file_name,
        raw_bytes=raw_bytes,
    )


def delete_image(table_name: str, image_id: str) -> None:
    """Delete storage object and metadata row."""
    client = get_user_client()
    row = client.table(table_name).select("*").eq("id", image_id).single().execute().data
    bucket = "variety-images" if table_name == "variety_images" else "review-images"
    client.storage.from_(bucket).remove([row["storage_path"]])
    client.table(table_name).delete().eq("id", image_id).execute()
    _clear_image_cache()


def _extract_signed_url(payload: dict | None) -> str | None:
    if not isinstance(payload, dict):
        return None
    return payload.get("signedURL") or payload.get("signedUrl") or payload.get("signed_url")


def _clear_image_cache() -> None:
    list_images_with_signed_urls.clear()
    list_primary_variety_images_with_signed_urls.clear()


@st.cache_data(ttl=300)
def list_images_with_signed_urls(table_name: str, relation_column: str, relation_id: str) -> list[dict]:
    """List image rows with signed URLs."""
    client = get_user_client()
    rows = client.table(table_name).select("*").eq(relation_column, relation_id).order("created_at").execute().data or []
    bucket = "variety-images" if table_name == "variety_images" else "review-images"
    enriched: list[dict] = []
    for row in rows:
        signed = client.storage.from_(bucket).create_signed_url(row["storage_path"], 3600)
        signed_url = _extract_signed_url(signed)
        enriched.append({**row, "signed_url": signed_url})
    return enriched


@st.cache_data(ttl=300)
def list_primary_variety_images_with_signed_urls(variety_ids: Sequence[str]) -> dict[str, dict]:
    """Return one representative image with signed URL for each variety."""
    ids = [str(variety_id) for variety_id in dict.fromkeys(variety_ids) if variety_id]
    if not ids:
        return {}
    client = get_user_client()
    rows = (
        client.table("variety_images")
        .select("id,variety_id,storage_path,file_name,mime_type,width,height,is_primary,created_at")
        .in_("variety_id", ids)
        .order("is_primary", desc=True)
        .order("created_at")
        .execute()
        .data
        or []
    )
    first_images: dict[str, dict] = {}
    for row in rows:
        variety_id = str(row.get("variety_id") or "")
        if not variety_id or variety_id in first_images:
            continue
        signed = client.storage.from_("variety-images").create_signed_url(row["storage_path"], 3600)
        first_images[variety_id] = {**row, "signed_url": _extract_signed_url(signed)}
    return first_images


def set_primary_variety_image(variety_id: str, image_id: str) -> None:
    """Set one primary variety image."""
    client = get_user_client()
    client.table("variety_images").update({"is_primary": False}).eq("variety_id", variety_id).execute()
    client.table("variety_images").update({"is_primary": True}).eq("id", image_id).eq("variety_id", variety_id).execute()
    _clear_image_cache()
