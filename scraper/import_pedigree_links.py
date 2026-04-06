"""Import pedigree links CSV into Supabase with idempotent upsert behavior."""

from __future__ import annotations

import csv
import os
from collections.abc import Iterable
from pathlib import Path

from scraper.utils.supabase_admin import get_admin_client

_REQUIRED_COLUMNS = (
    "id",
    "child_variety_id",
    "parent_variety_id",
    "parent_order",
    "crossed_year",
    "note",
    "created_at",
)
_DEFAULT_CSV_PATH = "database/imports/variety_parent_links.csv"
_BATCH_SIZE = max(1, int(os.getenv("SUPABASE_UPSERT_BATCH_SIZE", "200")))
_VALIDATE_ONLY = os.getenv("PEDIGREE_VALIDATE_ONLY", "0").strip().lower() in {"1", "true", "yes", "on"}


def _chunked(items: list[str], size: int) -> Iterable[list[str]]:
    for index in range(0, len(items), size):
        yield items[index : index + size]


def _clean(value: str | None) -> str:
    return (value or "").strip()


def _parse_required_int(raw: str | None, *, column: str, line_number: int) -> int:
    text = _clean(raw)
    if not text:
        raise ValueError(f"{line_number}行目: {column} は必須です。")
    try:
        return int(text)
    except ValueError as exc:
        raise ValueError(f"{line_number}行目: {column} は整数で入力してください。") from exc


def _parse_optional_int(raw: str | None, *, column: str, line_number: int) -> int | None:
    text = _clean(raw)
    if not text:
        return None
    try:
        return int(text)
    except ValueError as exc:
        raise ValueError(f"{line_number}行目: {column} は整数で入力してください。") from exc


def _load_rows(csv_path: Path) -> list[dict]:
    if not csv_path.exists():
        raise FileNotFoundError(f"CSVファイルが見つかりません: {csv_path}")

    with csv_path.open("r", encoding="utf-8-sig", newline="") as fp:
        reader = csv.DictReader(fp)
        if reader.fieldnames is None:
            raise ValueError("CSVヘッダーが読み取れません。")
        missing_columns = [column for column in _REQUIRED_COLUMNS if column not in reader.fieldnames]
        if missing_columns:
            raise ValueError(f"CSVに不足している列があります: {', '.join(missing_columns)}")

        rows: list[dict] = []
        id_to_key: dict[str, tuple[str, str, int]] = {}
        row_index_by_key: dict[tuple[str, str, int], int] = {}

        for line_number, raw in enumerate(reader, start=2):
            link_id = _clean(raw.get("id"))
            child_id = _clean(raw.get("child_variety_id"))
            parent_id = _clean(raw.get("parent_variety_id"))
            parent_order = _parse_required_int(raw.get("parent_order"), column="parent_order", line_number=line_number)
            crossed_year = _parse_optional_int(raw.get("crossed_year"), column="crossed_year", line_number=line_number)
            note = _clean(raw.get("note")) or None
            created_at = _clean(raw.get("created_at")) or None

            if not link_id:
                raise ValueError(f"{line_number}行目: id は必須です。")
            if not child_id:
                raise ValueError(f"{line_number}行目: child_variety_id は必須です。")
            if not parent_id:
                raise ValueError(f"{line_number}行目: parent_variety_id は必須です。")
            if parent_order not in {1, 2}:
                raise ValueError(f"{line_number}行目: parent_order は 1 または 2 を指定してください。")
            if child_id == parent_id:
                raise ValueError(f"{line_number}行目: child_variety_id と parent_variety_id は同一にできません。")
            key = (child_id, parent_id, parent_order)
            existing_key_for_id = id_to_key.get(link_id)
            if existing_key_for_id and existing_key_for_id != key:
                raise ValueError(f"{line_number}行目: id が重複しています ({link_id})")

            payload = {
                "id": link_id,
                "child_variety_id": child_id,
                "parent_variety_id": parent_id,
                "parent_order": parent_order,
                "crossed_year": crossed_year,
                "note": note,
            }
            if created_at:
                payload["created_at"] = created_at
            existing_row_index = row_index_by_key.get(key)
            if existing_row_index is None:
                row_index_by_key[key] = len(rows)
                rows.append(payload)
            else:
                replaced_id = rows[existing_row_index]["id"]
                if replaced_id != link_id:
                    id_to_key.pop(replaced_id, None)
                rows[existing_row_index] = payload
                print(
                    "[WARN] Duplicate key in CSV replaced by latest row: "
                    f"line={line_number}, child={child_id}, parent={parent_id}, parent_order={parent_order}"
                )
            id_to_key[link_id] = key

    return rows


def _resolve_variety_ids(client, rows: list[dict]) -> tuple[set[str], list[str]]:
    variety_ids = sorted(
        {
            str(row["child_variety_id"])
            for row in rows
            if row.get("child_variety_id")
        }
        | {
            str(row["parent_variety_id"])
            for row in rows
            if row.get("parent_variety_id")
        }
    )
    existing_ids: set[str] = set()
    for chunk in _chunked(variety_ids, 500):
        data = client.table("varieties").select("id").in_("id", chunk).execute().data or []
        existing_ids.update(str(row.get("id")) for row in data if row.get("id"))
    missing = [variety_id for variety_id in variety_ids if variety_id not in existing_ids]
    return existing_ids, missing


def _fetch_existing_links_by_key(client, child_variety_ids: list[str]) -> dict[tuple[str, str, int], str]:
    existing: dict[tuple[str, str, int], str] = {}
    for chunk in _chunked(child_variety_ids, 500):
        data = (
            client.table("variety_parent_links")
            .select("id,child_variety_id,parent_variety_id,parent_order")
            .in_("child_variety_id", chunk)
            .execute()
            .data
            or []
        )
        for row in data:
            key = (str(row["child_variety_id"]), str(row["parent_variety_id"]), int(row["parent_order"]))
            if key in existing and existing[key] != str(row["id"]):
                raise RuntimeError(
                    "既存データに同一キー重複が存在します: "
                    f"child={key[0]}, parent={key[1]}, parent_order={key[2]}"
                )
            existing[key] = str(row["id"])
    return existing


def _prepare_upsert_rows(rows: list[dict], existing_by_key: dict[tuple[str, str, int], str]) -> tuple[list[dict], int, int]:
    upsert_rows: list[dict] = []
    inserted = 0
    updated = 0
    for row in rows:
        key = (str(row["child_variety_id"]), str(row["parent_variety_id"]), int(row["parent_order"]))
        payload = dict(row)
        existing_id = existing_by_key.get(key)
        if existing_id:
            payload["id"] = existing_id
            payload.pop("created_at", None)
            updated += 1
        else:
            inserted += 1
        upsert_rows.append(payload)
    return upsert_rows, inserted, updated


def _upsert_rows(client, rows: list[dict]) -> None:
    for index in range(0, len(rows), _BATCH_SIZE):
        chunk = rows[index : index + _BATCH_SIZE]
        client.table("variety_parent_links").upsert(chunk, on_conflict="id").execute()


def main() -> None:
    csv_path = Path(os.getenv("PEDIGREE_CSV_PATH", _DEFAULT_CSV_PATH))
    rows = _load_rows(csv_path)
    print(f"[INFO] Loaded {len(rows)} pedigree links from {csv_path}.")

    if _VALIDATE_ONLY:
        print("[INFO] PEDIGREE_VALIDATE_ONLY is enabled. Validation completed without DB write.")
        return

    client = get_admin_client()
    existing_variety_ids, missing_variety_ids = _resolve_variety_ids(client, rows)
    if missing_variety_ids:
        preview = ", ".join(missing_variety_ids[:10])
        suffix = " ..." if len(missing_variety_ids) > 10 else ""
        print(f"[WARN] Missing variety IDs detected ({len(missing_variety_ids)}件): {preview}{suffix}")

    valid_rows = [
        row
        for row in rows
        if str(row["child_variety_id"]) in existing_variety_ids and str(row["parent_variety_id"]) in existing_variety_ids
    ]
    skipped_rows = len(rows) - len(valid_rows)
    if skipped_rows:
        print(f"[WARN] Skipped {skipped_rows} rows because child/parent variety IDs do not exist.")
    if not valid_rows:
        raise RuntimeError("インポート可能な行がありません。CSVの品種IDを確認してください。")

    child_variety_ids = sorted({str(row["child_variety_id"]) for row in valid_rows})
    existing_by_key = _fetch_existing_links_by_key(client, child_variety_ids)
    upsert_rows, inserted_count, updated_count = _prepare_upsert_rows(valid_rows, existing_by_key)
    _upsert_rows(client, upsert_rows)
    print(
        "[INFO] Import completed: "
        f"total={len(upsert_rows)}, inserted={inserted_count}, updated={updated_count}, skipped={skipped_rows}."
    )


if __name__ == "__main__":
    main()
