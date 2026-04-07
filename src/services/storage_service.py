"""Supabase Storage image management service."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import mimetypes
from pathlib import Path
from uuid import uuid4

from pydantic import ValidationError
from storage3.exceptions import StorageException
from storage3.types import CreateSignedUploadUrlOptions

from src.services.auth_service import get_user_client
from src.services.cache_service import bump_cache_scopes, scoped_cache_data
from src.utils.batching import chunked_sequence
from src.utils.image_utils import ALLOWED_MIME_TYPES, MAX_LONG_EDGE, MAX_UPLOAD_BYTES, process_image, validate_image_file

_VARIETY_IMAGE_LIMIT = 5
_REVIEW_IMAGE_LIMIT = 3
_POSTGREST_IN_CHUNK_SIZE = 200
_SIGNED_URL_FALLBACK_EXCEPTIONS = (TypeError, ValidationError, StorageException)
_MIME_EXTENSION_MAP = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def _safe_file_stem(name: str) -> str:
    stem = Path(name).stem.lower()
    safe = "".join(ch if ch.isalnum() or ch in ("_", "-") else "_" for ch in stem).strip("_")
    return safe[:80] or "image"


def _coerce_positive_int(value: object, *, field_name: str) -> int:
    try:
        numeric = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} が不正です。") from exc
    if numeric <= 0:
        raise ValueError(f"{field_name} が不正です。")
    return numeric


def _normalize_relation_id(value: object) -> str:
    relation_id = str(value or "").strip()
    if not relation_id:
        raise ValueError("関連IDが不正です。")
    return relation_id


def _normalize_client_file_entry(raw: Mapping[str, object]) -> dict[str, object]:
    client_file_id = str(raw.get("client_file_id") or raw.get("id") or "").strip()
    if not client_file_id:
        raise ValueError("アップロードファイル識別子が不正です。")

    file_name = str(raw.get("file_name") or "").strip()
    if not file_name:
        raise ValueError("ファイル名が不正です。")

    mime_type = str(raw.get("mime_type") or "").strip().lower()
    if mime_type not in ALLOWED_MIME_TYPES:
        raise ValueError("許可されていないMIMEタイプです。")

    file_size_bytes = _coerce_positive_int(raw.get("file_size_bytes"), field_name="file_size_bytes")
    if file_size_bytes > MAX_UPLOAD_BYTES:
        raise ValueError("ファイルサイズが上限50MBを超えています。")

    width = _coerce_positive_int(raw.get("width"), field_name="width")
    height = _coerce_positive_int(raw.get("height"), field_name="height")
    if max(width, height) > MAX_LONG_EDGE:
        raise ValueError(f"画像の長辺が上限{MAX_LONG_EDGE}pxを超えています。")

    extension = _MIME_EXTENSION_MAP.get(mime_type)
    if extension is None:
        raise ValueError("許可されていないMIMEタイプです。")

    return {
        "client_file_id": client_file_id,
        "file_name": file_name,
        "mime_type": mime_type,
        "file_size_bytes": file_size_bytes,
        "width": width,
        "height": height,
        "extension": extension,
    }


def _normalize_client_file_entries(
    raw_files: Sequence[Mapping[str, object]] | None,
    *,
    max_files: int,
) -> list[dict[str, object]]:
    if not raw_files:
        return []
    normalized: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    for raw in raw_files:
        if not isinstance(raw, Mapping):
            raise ValueError("画像メタデータが不正です。")
        entry = _normalize_client_file_entry(raw)
        client_file_id = str(entry["client_file_id"])
        if client_file_id in seen_ids:
            continue
        seen_ids.add(client_file_id)
        normalized.append(entry)
    if len(normalized) > max_files:
        raise ValueError(f"画像は最大{max_files}枚までです。")
    return normalized


def _normalize_storage_path(
    value: object,
    *,
    expected_prefix: str,
    expected_extension: str,
) -> str:
    storage_path = str(value or "").strip()
    if not storage_path:
        raise ValueError("ストレージパスが不正です。")
    if "\\" in storage_path or storage_path.startswith("/") or storage_path.endswith("/"):
        raise ValueError("ストレージパスが不正です。")
    segments = storage_path.split("/")
    if any(not segment or segment in (".", "..") for segment in segments):
        raise ValueError("ストレージパスが不正です。")
    if not storage_path.startswith(expected_prefix):
        raise ValueError("ストレージパスが不正です。")
    if not storage_path.endswith(expected_extension):
        raise ValueError("ストレージパスが不正です。")
    return storage_path


def _count_relation_images(client, *, table: str, relation_column: str, relation_id: str) -> int:
    response = client.table(table).select("id", count="exact", head=True).eq(relation_column, relation_id).execute()
    return int(response.count or 0)


def _list_relation_image_rows(client, *, table: str, relation_column: str, relation_id: str) -> list[dict[str, object]]:
    response = client.table(table).select("id, storage_path").eq(relation_column, relation_id).execute()
    rows = response.data or []
    if not isinstance(rows, list):
        return []
    return [dict(row) for row in rows if isinstance(row, Mapping)]


def _prepare_direct_upload_targets(
    *,
    bucket: str,
    base_path: str,
    table: str,
    relation_column: str,
    relation_id: str,
    files: Sequence[Mapping[str, object]] | None,
    max_files: int,
) -> list[dict]:
    safe_relation_id = _normalize_relation_id(relation_id)
    normalized_files = _normalize_client_file_entries(files, max_files=max_files)
    if not normalized_files:
        return []

    client = get_user_client()
    existing_count = _count_relation_images(
        client,
        table=table,
        relation_column=relation_column,
        relation_id=safe_relation_id,
    )
    if existing_count + len(normalized_files) > max_files:
        raise ValueError(f"画像は最大{max_files}枚までです。")

    targets: list[dict] = []
    storage_api = client.storage.from_(bucket)
    for file_entry in normalized_files:
        file_name = str(file_entry["file_name"])
        storage_path = (
            f"{base_path}/{safe_relation_id}/"
            f"{uuid4()}_{_safe_file_stem(file_name)}{file_entry['extension']}"
        )
        signed = storage_api.create_signed_upload_url(
            storage_path,
            CreateSignedUploadUrlOptions(upsert="false"),
        )
        signed_upload_url = _extract_signed_url(signed)
        if not signed_upload_url:
            client_file_id = str(file_entry.get("client_file_id") or "")
            raise RuntimeError(
                "署名付きアップロードURLの生成に失敗しました。"
                f" (client_file_id={client_file_id}, storage_path={storage_path})"
            )
        targets.append(
            {
                "client_file_id": file_entry["client_file_id"],
                "storage_path": storage_path,
                "signed_upload_url": signed_upload_url,
                "file_name": file_name,
                "mime_type": file_entry["mime_type"],
                "file_size_bytes": file_entry["file_size_bytes"],
                "width": file_entry["width"],
                "height": file_entry["height"],
            }
        )
    return targets


def _normalize_uploaded_file_entries(
    raw_uploaded_files: Sequence[Mapping[str, object]] | None,
    *,
    relation_id: str,
    base_path: str,
    max_files: int,
) -> list[dict[str, object]]:
    if not raw_uploaded_files:
        return []
    normalized: list[dict[str, object]] = []
    seen_storage_paths: set[str] = set()
    expected_prefix = f"{base_path}/{relation_id}/"
    for raw in raw_uploaded_files:
        if not isinstance(raw, Mapping):
            raise ValueError("アップロード結果が不正です。")
        base_entry = _normalize_client_file_entry(raw)
        storage_path = _normalize_storage_path(
            raw.get("storage_path"),
            expected_prefix=expected_prefix,
            expected_extension=str(base_entry["extension"]),
        )
        if storage_path in seen_storage_paths:
            continue
        seen_storage_paths.add(storage_path)
        normalized.append(
            {
                "storage_path": storage_path,
                "file_name": base_entry["file_name"],
                "mime_type": base_entry["mime_type"],
                "file_size_bytes": base_entry["file_size_bytes"],
                "width": base_entry["width"],
                "height": base_entry["height"],
            }
        )
    if len(normalized) > max_files:
        raise ValueError(f"画像は最大{max_files}枚までです。")
    return normalized


def _finalize_direct_uploads(
    *,
    bucket: str,
    table: str,
    relation_column: str,
    relation_id: str,
    base_path: str,
    uploaded_files: Sequence[Mapping[str, object]] | None,
    max_files: int,
) -> list[dict]:
    safe_relation_id = _normalize_relation_id(relation_id)
    normalized_uploaded = _normalize_uploaded_file_entries(
        uploaded_files,
        relation_id=safe_relation_id,
        base_path=base_path,
        max_files=max_files,
    )
    if not normalized_uploaded:
        return []

    client = get_user_client()
    existing_rows = _list_relation_image_rows(
        client,
        table=table,
        relation_column=relation_column,
        relation_id=safe_relation_id,
    )
    existing_by_storage_path = {
        str(row.get("storage_path") or ""): row for row in existing_rows if str(row.get("storage_path") or "").strip()
    }
    pending_inserts = [
        entry for entry in normalized_uploaded if str(entry["storage_path"]) not in existing_by_storage_path
    ]
    if len(existing_rows) + len(pending_inserts) > max_files:
        raise ValueError(f"画像は最大{max_files}枚までです。")
    if not pending_inserts:
        return []
    storage_api = client.storage.from_(bucket)
    missing_storage_paths = [str(entry["storage_path"]) for entry in pending_inserts if not storage_api.exists(str(entry["storage_path"]))]
    if missing_storage_paths:
        raise ValueError("アップロード済みファイルを確認できませんでした。再試行してください。")

    rows = [
        {
            "id": str(uuid4()),
            relation_column: safe_relation_id,
            "storage_path": str(entry["storage_path"]),
            "file_name": str(entry["file_name"]),
            "mime_type": str(entry["mime_type"]),
            "file_size_bytes": int(entry["file_size_bytes"]),
            "width": int(entry["width"]),
            "height": int(entry["height"]),
            **({"is_primary": index == 0 and not existing_rows} if table == "variety_images" else {}),
        }
        for index, entry in enumerate(pending_inserts)
    ]
    inserted = client.table(table).insert(rows).execute().data or []
    _clear_image_cache()
    return inserted


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
    is_primary = False
    if relation_column == "variety_id":
        is_primary = (
            _count_relation_images(
                client,
                table="variety_images",
                relation_column="variety_id",
                relation_id=relation_id,
            )
            == 0
        )
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
    if relation_column == "variety_id":
        metadata["is_primary"] = is_primary
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


def prepare_variety_image_direct_upload_targets(
    variety_id: str,
    files: Sequence[Mapping[str, object]] | None,
) -> list[dict]:
    """Create signed direct-upload targets for client-side variety image uploads."""
    return _prepare_direct_upload_targets(
        bucket="variety-images",
        base_path="varieties",
        table="variety_images",
        relation_column="variety_id",
        relation_id=variety_id,
        files=files,
        max_files=_VARIETY_IMAGE_LIMIT,
    )


def prepare_review_image_direct_upload_targets(
    review_id: str,
    files: Sequence[Mapping[str, object]] | None,
) -> list[dict]:
    """Create signed direct-upload targets for client-side review image uploads."""
    return _prepare_direct_upload_targets(
        bucket="review-images",
        base_path="reviews",
        table="review_images",
        relation_column="review_id",
        relation_id=review_id,
        files=files,
        max_files=_REVIEW_IMAGE_LIMIT,
    )


def finalize_variety_image_direct_uploads(
    variety_id: str,
    uploaded_files: Sequence[Mapping[str, object]] | None,
) -> list[dict]:
    """Persist metadata rows after client-side direct uploads for variety images."""
    return _finalize_direct_uploads(
        bucket="variety-images",
        table="variety_images",
        relation_column="variety_id",
        relation_id=variety_id,
        base_path="varieties",
        uploaded_files=uploaded_files,
        max_files=_VARIETY_IMAGE_LIMIT,
    )


def finalize_review_image_direct_uploads(
    review_id: str,
    uploaded_files: Sequence[Mapping[str, object]] | None,
) -> list[dict]:
    """Persist metadata rows after client-side direct uploads for review images."""
    return _finalize_direct_uploads(
        bucket="review-images",
        table="review_images",
        relation_column="review_id",
        relation_id=review_id,
        base_path="reviews",
        uploaded_files=uploaded_files,
        max_files=_REVIEW_IMAGE_LIMIT,
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


def _extract_signed_urls(payload: object, *, expected_count: int) -> list[str | None] | None:
    entries: list[object] | None = None
    if isinstance(payload, list):
        entries = payload
    elif isinstance(payload, Mapping):
        for key in ("data", "signedURLs", "signedUrls", "signed_urls"):
            candidate = payload.get(key)
            if isinstance(candidate, list):
                entries = candidate
                break
    if entries is None or len(entries) != expected_count:
        return None
    normalized: list[str | None] = []
    for entry in entries:
        normalized.append(_extract_signed_url(dict(entry) if isinstance(entry, Mapping) else None))
    return normalized


def _create_signed_url_or_none(bucket_api, storage_path: str, expires_in: int) -> str | None:
    try:
        return _extract_signed_url(bucket_api.create_signed_url(storage_path, expires_in))
    except _SIGNED_URL_FALLBACK_EXCEPTIONS:
        return None


def _create_signed_urls(bucket_api, storage_paths: Sequence[str], expires_in: int) -> list[str | None]:
    normalized_paths = [str(path) for path in storage_paths if str(path).strip()]
    if not normalized_paths:
        return []
    batch_method = getattr(bucket_api, "create_signed_urls", None)
    if callable(batch_method):
        try:
            batch_payload = batch_method(normalized_paths, expires_in)
        except _SIGNED_URL_FALLBACK_EXCEPTIONS:
            batch_payload = None
        else:
            signed_urls = _extract_signed_urls(batch_payload, expected_count=len(normalized_paths))
            if signed_urls is not None:
                return signed_urls
    return [_create_signed_url_or_none(bucket_api, path, expires_in) for path in normalized_paths]


def _clear_image_cache() -> None:
    list_images_with_signed_urls.clear()
    list_primary_variety_images_with_signed_urls.clear()
    bump_cache_scopes("storage")


@scoped_cache_data(ttl=300, scopes="storage")
def list_images_with_signed_urls(table_name: str, relation_column: str, relation_id: str) -> list[dict]:
    """List image rows with signed URLs."""
    client = get_user_client()
    query = client.table(table_name).select("*").eq(relation_column, relation_id)
    if table_name == "variety_images":
        query = query.order("is_primary", desc=True)
    rows = query.order("created_at").execute().data or []
    bucket = "variety-images" if table_name == "variety_images" else "review-images"
    bucket_api = client.storage.from_(bucket)
    signed_urls = _create_signed_urls(bucket_api, [str(row["storage_path"]) for row in rows], 3600)
    return [{**row, "signed_url": signed_url} for row, signed_url in zip(rows, signed_urls, strict=True)]


@scoped_cache_data(ttl=300, scopes="storage")
def list_primary_variety_images_with_signed_urls(variety_ids: Sequence[str]) -> dict[str, dict]:
    """Return one representative image with signed URL for each variety."""
    ids = [str(variety_id) for variety_id in dict.fromkeys(variety_ids) if variety_id]
    if not ids:
        return {}
    client = get_user_client()
    bucket_api = client.storage.from_("variety-images")
    first_images: dict[str, dict] = {}
    for id_chunk in chunked_sequence(ids, _POSTGREST_IN_CHUNK_SIZE):
        rows = (
            client.table("variety_images")
            .select("id,variety_id,storage_path,file_name,mime_type,width,height,is_primary,created_at")
            .in_("variety_id", id_chunk)
            .order("is_primary", desc=True)
            .order("created_at")
            .execute()
            .data
            or []
        )
        representative_rows: list[dict] = []
        for row in rows:
            variety_id = str(row.get("variety_id") or "")
            if not variety_id or variety_id in first_images:
                continue
            representative_rows.append(row)
        signed_urls = _create_signed_urls(
            bucket_api,
            [str(row["storage_path"]) for row in representative_rows],
            3600,
        )
        for row, signed_url in zip(representative_rows, signed_urls, strict=True):
            first_images[str(row.get("variety_id") or "")] = {**row, "signed_url": signed_url}
    return first_images


def set_primary_variety_image(variety_id: str, image_id: str) -> None:
    """Set one primary variety image."""
    client = get_user_client()
    image_row = (
        client.table("variety_images")
        .select("id,variety_id,is_primary")
        .eq("id", image_id)
        .eq("variety_id", variety_id)
        .maybe_single()
        .execute()
        .data
    )
    if not image_row:
        raise ValueError("指定した画像が見つかりません。")
    if bool(image_row.get("is_primary")):
        return
    client.table("variety_images").update({"is_primary": False}).eq("variety_id", variety_id).execute()
    client.table("variety_images").update({"is_primary": True}).eq("id", image_id).eq("variety_id", variety_id).execute()
    _clear_image_cache()
