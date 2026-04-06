"""Settings page."""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from src.components.layout import inject_app_style, render_page_header, render_section_title
from src.components.sidebar import render_sidebar
from src.config import get_config
from src.services.auth_service import require_admin_session
from src.services.export_service import export_table_csv
from src.services.scrape_service import (
    clear_scrape_cache,
    get_recent_variety_scrape_runs,
    get_variety_scrape_logs,
)

st.set_page_config(page_title="設定", layout="wide")
require_admin_session()
inject_app_style()
render_sidebar()
cfg = get_config()
render_page_header("設定", "エクスポート、ローカル品種取込、運用診断を管理します。")

render_section_title("データエクスポート")
export_tables = [
    "varieties",
    "variety_parent_links",
    "reviews",
    "notes",
    "variety_scrape_runs",
    "variety_scrape_logs",
]
for table in export_tables:
    st.download_button(
        f"{table} をCSVダウンロード",
        data=export_table_csv(table),
        file_name=f"{table}.csv",
        mime="text/csv",
        use_container_width=True,
    )

render_section_title("ローカル高速スクレイピング", "更新機能はローカルCLI実行に統一しました。")
st.info("この画面からの更新ボタンは廃止しました。以下のコマンドをローカル端末で実行してください。")
st.code(
    "\n".join(
        [
            "# PowerShell",
            '$env:SUPABASE_URL = "https://YOUR_PROJECT.supabase.co"',
            '$env:SUPABASE_SERVICE_ROLE_KEY = "YOUR_SERVICE_ROLE_KEY"',
            '$env:APP_TIMEZONE = "Asia/Tokyo"',
            '$env:MAFF_MIN_INTERVAL_SECONDS = "0"',
            '$env:MAFF_MAX_PAGES_PER_RUN = "200"',
            '$env:SUPABASE_UPSERT_BATCH_SIZE = "200"',
            "python -m scraper.main",
        ]
    )
)
if st.button("実行履歴を再読み込み", use_container_width=True):
    clear_scrape_cache()
    st.rerun()

render_section_title("最近の品種取得実行")
runs = get_recent_variety_scrape_runs()
st.dataframe(runs, use_container_width=True, hide_index=True)

selected_run_id = st.selectbox(
    "ログを確認する実行ID",
    [""] + [r["id"] for r in runs],
    format_func=lambda x: "選択してください" if not x else x,
)
if selected_run_id:
    logs = get_variety_scrape_logs(selected_run_id, limit=200)
    st.dataframe(logs, use_container_width=True, hide_index=True)

render_section_title("診断情報")
st.write(
    {
        "app_version": "v3.0.0",
        "timezone": cfg.app_timezone,
        "has_supabase_url": bool(cfg.supabase_url),
        "has_supabase_anon_key": bool(cfg.supabase_anon_key),
        "scrape_mode": "local_cli_only",
        "last_successful_variety_scrape": next(
            (r.get("finished_at") for r in runs if r.get("status") == "success"),
            None,
        ),
        "checked_at": datetime.utcnow().isoformat(),
    }
)
