"""Main scraper entrypoint for MAFF variety ingestion."""

from __future__ import annotations

import os
import traceback
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from src.constants.prefectures import PREFECTURES

from scraper.config import load_config
from scraper.sources.maff_scraper import MaffScraper
from scraper.utils.hashing import compute_variety_hash
from scraper.utils.normalization import normalize_text
from scraper.utils.supabase_admin import get_admin_client


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


def _upsert_variety(client, variety: dict) -> None:
    registration_number = normalize_text(variety.get("registration_number", ""))
    if not registration_number:
        raise ValueError("registration_number is missing.")
    payload = _build_variety_payload({**variety, "registration_number": registration_number})
    existing_rows = client.table("varieties").select("id").eq("registration_number", registration_number).limit(1).execute().data or []
    if existing_rows:
        client.table("varieties").update(payload).eq("id", existing_rows[0]["id"]).execute()
    else:
        client.table("varieties").insert({"id": str(uuid4()), **payload}).execute()


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
        for variety in varieties:
            processed_count += 1
            registration_number = variety.get("registration_number")
            name = variety.get("name")
            detail_url = variety.get("maff_detail_url")
            fetch_error = variety.get("_fetch_error")
            if fetch_error:
                failed_count += 1
                _safe_insert_log(
                    client,
                    run_id=run_id,
                    registration_number=registration_number,
                    variety_name=name,
                    detail_url=detail_url,
                    status="failed",
                    message=f"詳細ページ取得失敗: {fetch_error}"[:1500],
                )
                continue
            try:
                _upsert_variety(client, variety)
                upserted_count += 1
                fingerprint = compute_variety_hash(
                    registration_number or "",
                    name or "",
                    detail_url or "",
                )
                _safe_insert_log(
                    client,
                    run_id=run_id,
                    registration_number=registration_number,
                    variety_name=name,
                    detail_url=detail_url,
                    status="upserted",
                    message=f"fingerprint={fingerprint}",
                )
            except Exception as exc:
                failed_count += 1
                _safe_insert_log(
                    client,
                    run_id=run_id,
                    registration_number=registration_number,
                    variety_name=name,
                    detail_url=detail_url,
                    status="failed",
                    message=str(exc)[:1500],
                )
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
