"""Generate UUID-based pedigree import CSV from name-based research data."""

from __future__ import annotations

import os
from pathlib import Path

from scraper.pedigree_sync import (
    build_pedigree_artifacts,
    build_variety_records,
    load_research_rows,
    load_varieties_from_csv,
    write_import_csv,
    write_resolution_csv,
)
from scraper.utils.supabase_admin import get_admin_client

_DEFAULT_SOURCE_CSV_PATH = "strawberry_full_pedigree.csv"
_DEFAULT_IMPORT_CSV_PATH = "database/imports/variety_parent_links.csv"


def _load_varieties():
    csv_path = os.getenv("PEDIGREE_VARIETIES_CSV_PATH", "").strip()
    if csv_path:
        return load_varieties_from_csv(Path(csv_path))

    client = get_admin_client()
    rows = (
        client.table("varieties")
        .select("id,name,alias_names,registered_year,source_system,deleted_at")
        .is_("deleted_at", "null")
        .order("name")
        .execute()
        .data
        or []
    )
    return build_variety_records(rows)


def main() -> None:
    source_csv_path = Path(os.getenv("PEDIGREE_SOURCE_CSV_PATH", _DEFAULT_SOURCE_CSV_PATH))
    import_csv_path = Path(os.getenv("PEDIGREE_IMPORT_CSV_PATH", _DEFAULT_IMPORT_CSV_PATH))
    resolution_csv_path = os.getenv("PEDIGREE_RESOLUTION_CSV_PATH", "").strip()

    research_rows = load_research_rows(source_csv_path)
    varieties = _load_varieties()
    artifacts = build_pedigree_artifacts(research_rows, varieties)
    write_import_csv(import_csv_path, artifacts.import_rows)
    if resolution_csv_path:
        write_resolution_csv(Path(resolution_csv_path), artifacts.resolutions)

    existing_resolutions = sum(1 for item in artifacts.resolutions if item.resolution_kind == "existing")
    placeholder_resolutions = sum(1 for item in artifacts.resolutions if item.resolution_kind == "placeholder")
    print(
        "[INFO] Generated pedigree import CSV: "
        f"source_rows={len(research_rows)}, import_rows={len(artifacts.import_rows)}, "
        f"placeholder_payloads={len(artifacts.placeholder_payloads)}, "
        f"existing_resolutions={existing_resolutions}, placeholder_resolutions={placeholder_resolutions}, "
        f"duplicate_replacements={artifacts.duplicate_replacements}, output={import_csv_path}"
    )
    if resolution_csv_path:
        print(f"[INFO] Wrote resolution audit CSV: {resolution_csv_path}")


if __name__ == "__main__":
    main()
