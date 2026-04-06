"""Settings page."""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from src.components.layout import inject_app_style, render_page_header, render_section_title
from src.components.sidebar import render_sidebar
from src.config import get_config
from src.core.github_client import GitHubClient
from src.services.auth_service import require_admin_session
from src.services.export_service import export_table_csv
from src.services.scrape_service import (
    dispatch_scraper_workflow,
    get_recent_variety_scrape_runs,
    get_variety_scrape_logs,
    poll_workflow_status,
)

st.set_page_config(page_title="設定", layout="wide")
require_admin_session()
inject_app_style()
render_sidebar()
cfg = get_config()
gh = GitHubClient(cfg)
render_page_header("設定", "エクスポート、手動品種取得、運用診断を管理します。")

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

render_section_title("手動品種スクレイピング", "MAFFの品種登録データ（Fragaria L.）を取得して反映します。")
if gh.is_ref_pinned_to_commit():
    st.warning(
        "GITHUB_REF がコミットSHAに設定されています。最新コードを使うには "
        "`main`（または `refs/heads/main`）を指定してください。"
    )
if st.button("MAFFから品種データを取得", use_container_width=True):
    try:
        dispatch_scraper_workflow()
        st.success("workflow_dispatch を送信しました。")
        with st.spinner("実行状況を確認中..."):
            run = poll_workflow_status(timeout_seconds=180, interval_seconds=5)
        if run:
            st.info(f"状態: {run.status} / 結果: {run.conclusion}")
            st.link_button("実行URLを開く", run.html_url)
    except Exception as exc:
        st.error(str(exc))

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
        "has_github_token": bool(cfg.github_token),
        "github_workflow_file": cfg.github_workflow_file,
        "github_ref_configured": cfg.github_ref,
        "github_ref_effective": gh.get_dispatch_ref(),
        "last_successful_variety_scrape": next(
            (r.get("finished_at") for r in runs if r.get("status") == "success"),
            None,
        ),
        "checked_at": datetime.utcnow().isoformat(),
    }
)
