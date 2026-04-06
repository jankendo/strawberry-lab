"""Main scraper entrypoint for MAFF variety ingestion."""

from __future__ import annotations

import mimetypes
import os
import re
import traceback
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TypeVar
from urllib.parse import urlparse
from uuid import uuid4

import requests

from src.constants.prefectures import PREFECTURES

from scraper.config import load_config
from scraper.sources.maff_scraper import MaffScraper
from scraper.utils.hashing import compute_variety_hash
from scraper.utils.normalization import normalize_text
from scraper.utils.supabase_admin import get_admin_client

_UPSERT_BATCH_SIZE = max(1, int(os.getenv("SUPABASE_UPSERT_BATCH_SIZE", "200")))
_LOG_INSERT_BATCH_SIZE = max(1, int(os.getenv("SCRAPE_LOG_BATCH_SIZE", "300")))
_FETCH_MAFF_IMAGES = os.getenv("MAFF_FETCH_IMAGES", "1").lower() not in {"0", "false", "no"}
_MAX_IMAGES_PER_VARIETY = max(1, min(5, int(os.getenv("MAFF_MAX_IMAGES_PER_VARIETY", "3"))))
_MAFF_IMAGE_TIMEOUT_SECONDS = max(5, int(os.getenv("MAFF_IMAGE_TIMEOUT_SECONDS", "20")))
_MAFF_IMAGE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    "Referer": "https://www.hinshu2.maff.go.jp/vips/cmm/apCMM110.aspx?MOSS=1",
}
_T = TypeVar("_T")


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _trim(value: str | None, max_length: int) -> str | None:
    if value is None:
        return None
    cleaned = normalize_text(value)
    return cleaned[:max_length] if cleaned else None


def _extract_prefecture(breeding_place: str | None) -> str | None:
    if not breeding_place:
        return None
    for prefecture in PREFECTURES:
        if prefecture in breeding_place:
            return prefecture
    return None


def _create_run(client) -> str:
    github_run_id = os.getenv("GITHUB_RUN_ID")
    github_server_url = os.getenv("GITHUB_SERVER_URL")
    github_repository = os.getenv("GITHUB_REPOSITORY")
    run_url = None
    if github_run_id and github_server_url and github_repository:
        run_url = f"{github_server_url}/{github_repository}/actions/runs/{github_run_id}"
    run = (
        client.table("variety_scrape_runs")
        .insert(
            {
                "trigger_type": "manual",
                "status": "running",
                "github_run_id": int(github_run_id) if github_run_id else None,
                "github_run_url": run_url,
                "started_at": _now_iso(),
            }
        )
        .execute()
        .data[0]
    )
    return run["id"]


def _finish_run(
    client,
    run_id: str,
    *,
    status: str,
    listed_count: int,
    processed_count: int,
    upserted_count: int,
    failed_count: int,
    error_message: str | None = None,
) -> None:
    client.table("variety_scrape_runs").update(
        {
            "status": status,
            "finished_at": _now_iso(),
            "listed_count": listed_count,
            "processed_count": processed_count,
            "upserted_count": upserted_count,
            "failed_count": failed_count,
            "error_message": error_message,
        }
    ).eq("id", run_id).execute()


def _insert_log(
    client,
    *,
    run_id: str,
    registration_number: str | None,
    variety_name: str | None,
    detail_url: str | None,
    status: str,
    message: str | None,
) -> None:
    client.table("variety_scrape_logs").insert(
        {
            "variety_scrape_run_id": run_id,
            "registration_number": registration_number,
            "variety_name": variety_name,
            "detail_url": detail_url,
            "status": status,
            "message": message,
        }
    ).execute()


def _safe_insert_log(
    client,
    *,
    run_id: str,
    registration_number: str | None,
    variety_name: str | None,
    detail_url: str | None,
    status: str,
    message: str | None,
) -> None:
    try:
        _insert_log(
            client,
            run_id=run_id,
            registration_number=registration_number,
            variety_name=variety_name,
            detail_url=detail_url,
            status=status,
            message=message,
        )
    except Exception as exc:
        print(f"[WARN] Failed to insert variety scrape log: {exc}")


def _safe_insert_logs_batch(client, logs: list[dict]) -> None:
    if not logs:
        return
    try:
        client.table("variety_scrape_logs").insert(logs).execute()
    except Exception as exc:
        print(f"[WARN] Failed to insert variety scrape logs batch ({len(logs)}): {exc}")
        for log in logs:
            _safe_insert_log(
                client,
                run_id=log["variety_scrape_run_id"],
                registration_number=log.get("registration_number"),
                variety_name=log.get("variety_name"),
                detail_url=log.get("detail_url"),
                status=log["status"],
                message=log.get("message"),
            )


def _chunked(items: list[_T], size: int) -> list[list[_T]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def _build_log_payload(
    run_id: str,
    *,
    registration_number: str | None,
    variety_name: str | None,
    detail_url: str | None,
    status: str,
    message: str | None,
) -> dict:
    return {
        "variety_scrape_run_id": run_id,
        "registration_number": registration_number,
        "variety_name": variety_name,
        "detail_url": detail_url,
        "status": status,
        "message": message,
    }


def _safe_image_token(value: str) -> str:
    token = re.sub(r"[^a-zA-Z0-9_-]+", "_", value).strip("_")
    return token[:80] or "maff_image"


def _guess_image_extension(image_url: str, content_type: str | None) -> str:
    ext = os.path.splitext(urlparse(image_url).path)[1].lower()
    if ext in {".jpg", ".jpeg", ".png", ".webp"}:
        return ext
    guessed = mimetypes.guess_extension((content_type or "").split(";")[0].strip().lower()) or ".jpg"
    if guessed == ".jpe":
        guessed = ".jpg"
    return guessed if guessed in {".jpg", ".jpeg", ".png", ".webp"} else ".jpg"


def _delete_storage_objects(client, paths: list[str]) -> None:
    if not paths:
        return
    try:
        client.storage.from_("variety-images").remove(paths)
    except Exception as exc:
        print(f"[WARN] Failed to remove stale MAFF images from storage: {exc}")


def _sync_variety_images(
    client,
    *,
    variety_id: str,
    registration_number: str,
    image_urls: list[str] | None,
) -> tuple[int, int, str | None]:
    if not _FETCH_MAFF_IMAGES:
        return (0, 0, "画像同期は MAFF_FETCH_IMAGES=0 のため無効です。")
    if not image_urls:
        return (0, 0, None)

    normalized_urls: list[str] = []
    for url in image_urls:
        cleaned = (url or "").strip()
        if cleaned and cleaned not in normalized_urls:
            normalized_urls.append(cleaned)
    target_urls = normalized_urls[:_MAX_IMAGES_PER_VARIETY]
    if not target_urls:
        return (0, 0, None)

    maff_prefix = f"varieties/{variety_id}/maff/"
    existing_rows = (
        client.table("variety_images")
        .select("id,storage_path,is_primary")
        .eq("variety_id", variety_id)
        .execute()
        .data
        or []
    )
    existing_primary = any(bool(row.get("is_primary")) for row in existing_rows)
    existing_maff = [row for row in existing_rows if str(row.get("storage_path", "")).startswith(maff_prefix)]

    desired_items: list[tuple[str, str]] = []
    for index, image_url in enumerate(target_urls, start=1):
        guessed_ext = _guess_image_extension(image_url, None)
        desired_items.append((image_url, f"{maff_prefix}{_safe_image_token(registration_number)}_{index}{guessed_ext}"))
    desired_paths = [item[1] for item in desired_items]

    stale_rows = [row for row in existing_maff if row.get("storage_path") not in set(desired_paths)]
    stale_paths = [row["storage_path"] for row in stale_rows if row.get("storage_path")]
    if stale_paths:
        _delete_storage_objects(client, stale_paths)
        stale_ids = [row["id"] for row in stale_rows if row.get("id")]
        if stale_ids:
            try:
                client.table("variety_images").delete().in_("id", stale_ids).execute()
            except Exception as exc:
                print(f"[WARN] Failed to remove stale MAFF image rows: {exc}")

    current_rows = (
        client.table("variety_images")
        .select("id,storage_path,is_primary")
        .eq("variety_id", variety_id)
        .execute()
        .data
        or []
    )
    current_by_path = {row["storage_path"]: row for row in current_rows if row.get("storage_path")}
    current_count = len(current_rows)
    synced_count = 0
    errors: list[str] = []

    for image_url, storage_path in desired_items:
        try:
            response = requests.get(image_url, headers=_MAFF_IMAGE_HEADERS, timeout=_MAFF_IMAGE_TIMEOUT_SECONDS)
            response.raise_for_status()
            content = response.content
            if not content:
                raise ValueError("empty image response")

            content_type = response.headers.get("Content-Type", "image/jpeg").split(";")[0].strip().lower()
            if not content_type.startswith("image/"):
                raise ValueError(f"unexpected content-type: {content_type}")
            existing_row = current_by_path.get(storage_path)

            if existing_row is None and current_count >= 5:
                errors.append(f"画像上限到達のため追加不可: {image_url}")
                continue

            client.storage.from_("variety-images").upload(
                path=storage_path,
                file=content,
                file_options={"content-type": content_type, "upsert": "true"},
            )
            metadata = {
                "variety_id": variety_id,
                "storage_path": storage_path,
                "file_name": os.path.basename(storage_path),
                "mime_type": content_type or "image/jpeg",
                "file_size_bytes": len(content),
                "width": None,
                "height": None,
            }
            if existing_row:
                client.table("variety_images").update(metadata).eq("id", existing_row["id"]).execute()
            else:
                create_payload = {
                    "id": str(uuid4()),
                    **metadata,
                    "is_primary": bool(not existing_primary and synced_count == 0),
                }
                client.table("variety_images").insert(create_payload).execute()
                current_count += 1
                if create_payload["is_primary"]:
                    existing_primary = True
            synced_count += 1
        except Exception as exc:
            errors.append(f"{image_url} ({exc})")

    if errors:
        return (synced_count, len(errors), " / ".join(errors[:3])[:1200])
    return (synced_count, 0, None)


def _ensure_required_schema(client) -> None:
    checks: list[tuple[str, Callable[[], object]]] = [
        (
            "table public.variety_scrape_runs",
            lambda: client.table("variety_scrape_runs").select("id").limit(1).execute(),
        ),
        (
            "table public.variety_scrape_logs",
            lambda: client.table("variety_scrape_logs").select("id").limit(1).execute(),
        ),
        (
            "table public.variety_images",
            lambda: client.table("variety_images").select("id,storage_path,variety_id").limit(1).execute(),
        ),
        (
            "MAFF columns on public.varieties",
            lambda: client.table("varieties")
            .select(
                "id,registration_number,application_number,registration_date,application_date,publication_date,"
                "scientific_name,japanese_name,breeder_right_holder,applicant,breeding_place,characteristics_summary,"
                "right_duration,usage_conditions,remarks,maff_detail_url,last_scraped_at,source_system"
            )
            .limit(1)
            .execute(),
        ),
    ]
    failures: list[str] = []
    for name, operation in checks:
        try:
            operation()
        except Exception as exc:
            failures.append(f"- {name}: {exc}")
    if failures:
        raise RuntimeError(
            "Supabaseスキーマが最新版ではありません。"
            " `database/supabase_all_in_one.sql` を再実行してください。\n"
            + "\n".join(failures)
        )


def _build_variety_payload(variety: dict) -> dict:
    registration_date = variety.get("registration_date")
    registered_year = int(registration_date[:4]) if registration_date else None
    characteristics_summary = _trim(variety.get("characteristics_summary"), 5000)
    breeding_place = _trim(variety.get("breeding_place"), 500)
    applicant = _trim(variety.get("applicant"), 200)
    breeder_right_holder = _trim(variety.get("breeder_right_holder"), 300)
    return {
        "registration_number": _trim(variety.get("registration_number"), 100),
        "application_number": _trim(variety.get("application_number"), 100),
        "registration_date": registration_date,
        "application_date": variety.get("application_date"),
        "publication_date": variety.get("publication_date"),
        "name": _trim(variety.get("name"), 100) or "名称不明",
        "scientific_name": _trim(variety.get("scientific_name"), 300),
        "japanese_name": _trim(variety.get("japanese_name"), 300),
        "breeder_right_holder": breeder_right_holder,
        "applicant": applicant,
        "breeding_place": breeding_place,
        "developer": applicant or breeder_right_holder,
        "registered_year": registered_year,
        "description": characteristics_summary,
        "characteristics_summary": characteristics_summary,
        "right_duration": _trim(variety.get("right_duration"), 500),
        "usage_conditions": _trim(variety.get("usage_conditions"), 5000),
        "remarks": _trim(variety.get("remarks"), 5000),
        "maff_detail_url": _trim(variety.get("maff_detail_url"), 1000),
        "last_scraped_at": _now_iso(),
        "source_system": "maff",
        "origin_prefecture": _extract_prefecture(breeding_place),
        "alias_names": [],
        "skin_color": None,
        "flesh_color": None,
        "brix_min": None,
        "brix_max": None,
        "acidity_level": "unknown",
        "harvest_start_month": None,
        "harvest_end_month": None,
        "tags": [],
        "deleted_at": None,
    }


def _load_existing_variety_ids(client, registration_numbers: list[str]) -> dict[str, str]:
    existing: dict[str, str] = {}
    unique_numbers = sorted({number for number in registration_numbers if number})
    if not unique_numbers:
        return existing
    for chunk in _chunked(unique_numbers, _UPSERT_BATCH_SIZE):
        rows = (
            client.table("varieties")
            .select("id,registration_number")
            .in_("registration_number", chunk)
            .is_("deleted_at", "null")
            .execute()
            .data
            or []
        )
        for row in rows:
            registration_number = row.get("registration_number")
            row_id = row.get("id")
            if registration_number and row_id:
                existing[registration_number] = row_id
    return existing


def run_scraper() -> int:
    """Run MAFF variety scraping and upsert to varieties table."""
    cfg = load_config()
    source_cfg = cfg.sources["maff"]
    client = get_admin_client()
    run_id: str | None = None
    listed_count = processed_count = upserted_count = failed_count = 0
    try:
        print("[INFO] Starting MAFF variety scraper.")
        _ensure_required_schema(client)
        print("[INFO] Schema preflight passed.")
        run_id = _create_run(client)
        scraper = MaffScraper(source_cfg)
        varieties = scraper.fetch_varieties()
        listed_count = len(varieties)
        print(f"[INFO] Listed records: {listed_count}")
        if not run_id:
            raise RuntimeError("Scrape run ID was not created.")

        pending_logs: list[dict] = []
        prepared_rows: list[dict] = []
        row_contexts: list[dict] = []
        upserted_contexts: list[dict] = []

        for variety in varieties:
            processed_count += 1
            registration_number = variety.get("registration_number")
            name = variety.get("name")
            detail_url = variety.get("maff_detail_url")
            fetch_error = variety.get("_fetch_error")
            if fetch_error:
                failed_count += 1
                pending_logs.append(
                    _build_log_payload(
                        run_id,
                        registration_number=registration_number,
                        variety_name=name,
                        detail_url=detail_url,
                        status="failed",
                        message=f"詳細ページ取得失敗: {fetch_error}"[:1500],
                    )
                )
                continue
            try:
                normalized_registration_number = normalize_text(variety.get("registration_number", ""))
                if not normalized_registration_number:
                    raise ValueError("registration_number is missing.")
                payload = _build_variety_payload({**variety, "registration_number": normalized_registration_number})
                prepared_rows.append(payload)
                row_contexts.append(
                    {
                        "registration_number": normalized_registration_number,
                        "name": payload.get("name"),
                        "detail_url": payload.get("maff_detail_url"),
                        "detail_image_urls": variety.get("detail_image_urls", []),
                    }
                )
            except Exception as exc:
                failed_count += 1
                pending_logs.append(
                    _build_log_payload(
                        run_id,
                        registration_number=registration_number,
                        variety_name=name,
                        detail_url=detail_url,
                        status="failed",
                        message=str(exc)[:1500],
                    )
                )

            if len(pending_logs) >= _LOG_INSERT_BATCH_SIZE:
                _safe_insert_logs_batch(client, pending_logs)
                pending_logs.clear()

        existing_map = _load_existing_variety_ids(
            client,
            [context["registration_number"] for context in row_contexts],
        )

        for row_batch, context_batch in zip(
            _chunked(prepared_rows, _UPSERT_BATCH_SIZE),
            _chunked(row_contexts, _UPSERT_BATCH_SIZE),
            strict=True,
        ):
            records: list[dict] = []
            context_with_ids: list[dict] = []
            for payload, context in zip(row_batch, context_batch, strict=True):
                registration_number = context["registration_number"]
                row_id = existing_map.get(registration_number)
                if not row_id:
                    row_id = str(uuid4())
                    existing_map[registration_number] = row_id
                records.append({"id": row_id, **payload})
                context_with_ids.append({**context, "variety_id": row_id})
            try:
                client.table("varieties").upsert(records, on_conflict="id").execute()
                for context in context_with_ids:
                    upserted_count += 1
                    upserted_contexts.append(context)
            except Exception as batch_exc:
                print(f"[WARN] Batched upsert failed; retrying row-by-row: {batch_exc}")
                for record, context in zip(records, context_with_ids, strict=True):
                    try:
                        client.table("varieties").upsert(record, on_conflict="id").execute()
                        upserted_count += 1
                        upserted_contexts.append(context)
                    except Exception as row_exc:
                        failed_count += 1
                        pending_logs.append(
                            _build_log_payload(
                                run_id,
                                registration_number=context.get("registration_number"),
                                variety_name=context.get("name"),
                                detail_url=context.get("detail_url"),
                                status="failed",
                                message=str(row_exc)[:1500],
                            )
                        )

            if len(pending_logs) >= _LOG_INSERT_BATCH_SIZE:
                _safe_insert_logs_batch(client, pending_logs)
                pending_logs.clear()

        for context in upserted_contexts:
            synced_count, image_error_count, image_error_message = _sync_variety_images(
                client,
                variety_id=context["variety_id"],
                registration_number=context.get("registration_number", ""),
                image_urls=context.get("detail_image_urls"),
            )
            if image_error_count > 0:
                failed_count += 1
                status = "failed"
            else:
                status = "upserted"
            fingerprint = compute_variety_hash(
                context.get("registration_number", ""),
                context.get("name", ""),
                context.get("detail_url", ""),
            )
            base_message = (
                f"fingerprint={fingerprint} images_synced={synced_count} image_errors={image_error_count}"
            )
            if image_error_message:
                base_message = f"{base_message} details={image_error_message}"
            pending_logs.append(
                _build_log_payload(
                    run_id,
                    registration_number=context.get("registration_number"),
                    variety_name=context.get("name"),
                    detail_url=context.get("detail_url"),
                    status=status,
                    message=base_message[:1500],
                )
            )
            if len(pending_logs) >= _LOG_INSERT_BATCH_SIZE:
                _safe_insert_logs_batch(client, pending_logs)
                pending_logs.clear()

        if pending_logs:
            _safe_insert_logs_batch(client, pending_logs)

        error_message = None
        if listed_count == 0:
            status = "error"
            error_message = "MAFF一覧の取得件数が0件でした。検索条件またはアクセス制御を確認してください。"
            _safe_insert_log(
                client,
                run_id=run_id,
                registration_number=None,
                variety_name=None,
                detail_url=source_cfg.search_url,
                status="failed",
                message=error_message,
            )
        elif failed_count == 0:
            status = "success"
        elif upserted_count == 0:
            status = "error"
        else:
            status = "partial_success"
        if run_id:
            _finish_run(
                client,
                run_id,
                status=status,
                listed_count=listed_count,
                processed_count=processed_count,
                upserted_count=upserted_count,
                failed_count=failed_count,
                error_message=error_message,
            )
        print(
            f"[INFO] Finished: status={status} listed={listed_count} processed={processed_count} "
            f"upserted={upserted_count} failed={failed_count}"
        )
        return 0 if status in ("success", "partial_success") else 1
    except Exception as exc:
        if run_id:
            _finish_run(
                client,
                run_id,
                status="error",
                listed_count=listed_count,
                processed_count=processed_count,
                upserted_count=upserted_count,
                failed_count=max(failed_count, 1),
                error_message=str(exc)[:1500],
            )
        print(f"[ERROR] Scraper aborted: {exc}")
        print(traceback.format_exc(limit=8))
        return 1


if __name__ == "__main__":
    raise SystemExit(run_scraper())
