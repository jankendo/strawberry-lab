"""Settings page."""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from src.config import get_config
from src.components.sidebar import render_sidebar
from src.services.auth_service import require_admin_session
from src.services.export_service import export_table_csv
from src.services.scrape_service import dispatch_scraper_workflow, get_recent_scrape_runs, poll_workflow_status

st.set_page_config(page_title="設定", layout="wide")
require_admin_session()
render_sidebar()
st.title("設定")

st.subheader("データエクスポート")
for table in ["varieties", "variety_parent_links", "reviews", "notes", "scraped_articles", "scrape_runs", "scrape_source_logs"]:
    st.download_button(
        f"{table} をCSVダウンロード",
        data=export_table_csv(table),
        file_name=f"{table}.csv",
        mime="text/csv",
    )

st.subheader("手動スクレイプ実行")
source = st.selectbox("ソース", ["all", "maff", "naro", "ja_news"])
if st.button("スクレイプ開始"):
    try:
        dispatch_scraper_workflow(source)
        st.success("workflow_dispatch を送信しました。")
        with st.spinner("実行状況を確認中..."):
            run = poll_workflow_status(timeout_seconds=120, interval_seconds=5)
        if run:
            st.info(f"状態: {run.status} / 結果: {run.conclusion}")
            st.link_button("実行URLを開く", run.html_url)
    except Exception as exc:
        st.error(str(exc))

st.subheader("最近のスクレイプ実行")
st.dataframe(get_recent_scrape_runs(), use_container_width=True, hide_index=True)

st.subheader("診断情報")
cfg = get_config()
st.write(
    {
        "app_version": "v2.0.0",
        "timezone": cfg.app_timezone,
        "has_supabase_url": bool(cfg.supabase_url),
        "has_supabase_anon_key": bool(cfg.supabase_anon_key),
        "has_github_token": bool(cfg.github_token),
        "last_successful_scrape": next((r.get("finished_at") for r in get_recent_scrape_runs() if r.get("status") == "success"), None),
        "checked_at": datetime.utcnow().isoformat(),
    }
)
