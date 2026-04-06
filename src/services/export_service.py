"""CSV export service."""

from __future__ import annotations

from io import StringIO

import pandas as pd

from src.services.auth_service import get_user_client
from src.utils.dataframe_utils import format_export_dataframe

EXPORT_TABLES = {
    "varieties": "varieties",
    "variety_parent_links": "variety_parent_links",
    "reviews": "reviews",
    "notes": "notes",
    "scraped_articles": "scraped_articles",
    "scrape_runs": "scrape_runs",
    "scrape_source_logs": "scrape_source_logs",
}

ORDER_COLUMNS = {
    "varieties": "created_at",
    "variety_parent_links": "created_at",
    "reviews": "created_at",
    "notes": "created_at",
    "scraped_articles": "scraped_at",
    "scrape_runs": "started_at",
    "scrape_source_logs": "started_at",
}


def export_table_csv(table_name: str) -> bytes:
    """Export table rows as UTF-8 BOM CSV."""
    if table_name not in EXPORT_TABLES:
        raise ValueError("Unsupported table export target.")
    client = get_user_client()
    rows = (
        client.table(EXPORT_TABLES[table_name])
        .select("*")
        .order(ORDER_COLUMNS[table_name], desc=False)
        .execute()
        .data
        or []
    )
    df = format_export_dataframe(pd.DataFrame(rows))
    out = StringIO()
    df.to_csv(out, index=False)
    return ("\ufeff" + out.getvalue()).encode("utf-8")
