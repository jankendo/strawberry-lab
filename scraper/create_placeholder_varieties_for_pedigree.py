"""Create placeholder varieties required by pedigree sync."""

from __future__ import annotations

import os
from pathlib import Path

from scraper.pedigree_sync import build_placeholder_payloads, build_variety_records, chunked, collect_placeholder_specs, load_research_rows
from scraper.utils.supabase_admin import get_admin_client

_DEFAULT_SOURCE_CSV_PATH = "strawberry_full_pedigree.csv"
_BATCH_SIZE = max(1, int(os.getenv("SUPABASE_UPSERT_BATCH_SIZE", "200")))
_VALIDATE_ONLY = os.getenv("PEDIGREE_PLACEHOLDER_VALIDATE_ONLY", "0").strip().lower() in {"1", "true", "yes", "on"}


def main() -> None:
    source_csv_path = Path(os.getenv("PEDIGREE_SOURCE_CSV_PATH", _DEFAULT_SOURCE_CSV_PATH))
    research_rows = load_research_rows(source_csv_path)

    client = get_admin_client()
    variety_rows = (
        client.table("varieties")
        .select("id,name,alias_names,registered_year,source_system,deleted_at")
        .is_("deleted_at", "null")
        .order("name")
        .execute()
        .data
        or []
    )
    varieties = build_variety_records(variety_rows)
    specs = collect_placeholder_specs(research_rows, varieties)
    payloads = build_placeholder_payloads(specs)
    print(
        "[INFO] Placeholder variety audit: "
        f"source_rows={len(research_rows)}, existing_varieties={len(varieties)}, placeholders={len(payloads)}."
    )
    if not payloads:
        print("[INFO] No placeholder varieties are required.")
        return
    if _VALIDATE_ONLY:
        print("[INFO] PEDIGREE_PLACEHOLDER_VALIDATE_ONLY is enabled. Validation completed without DB write.")
        return

    for payload_batch in chunked(payloads, _BATCH_SIZE):
        client.table("varieties").upsert(payload_batch, on_conflict="id").execute()
    print(f"[INFO] Upserted placeholder varieties: {len(payloads)}")


if __name__ == "__main__":
    main()
