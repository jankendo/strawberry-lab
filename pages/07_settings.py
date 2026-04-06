"""Settings page."""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from src.components.layout import (
    inject_app_style,
    render_action_bar,
    render_empty_state,
    render_hero_banner,
    render_kpi_cards,
    render_section_title,
    render_surface,
)
from src.components.sidebar import render_sidebar
from src.config import get_config
from src.services.auth_service import get_auth_persistence_status, require_admin_session
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
render_hero_banner(
    "設定",
    "データエクスポート、ローカル取込運用、診断確認を一画面で管理します。",
    eyebrow="運用管理",
    chips=["CSVエクスポート", "取込履歴確認", "診断チェック"],
)
render_action_bar(
    title="管理メニュー",
    description="必要なテーブルをエクスポートし、ローカル取込の実行履歴と診断情報を定期的に確認してください。",
    actions=["CSVを取得", "履歴を更新", "ログを確認", "診断を点検"],
)

render_section_title("データエクスポート", "主要テーブルを用途別にCSVダウンロードできます。")
render_surface("分析共有やバックアップ用途に合わせて必要なテーブルだけ取得できます。", tone="soft")
export_tables = [
    "varieties",
    "variety_parent_links",
    "reviews",
    "notes",
    "variety_scrape_runs",
    "variety_scrape_logs",
]
export_columns = st.columns(3, gap="small")
for index, table in enumerate(export_tables):
    with export_columns[index % len(export_columns)]:
        with st.container(border=True):
            st.markdown(f"`{table}`")
            st.download_button(
                f"{table} をCSVダウンロード",
                data=export_table_csv(table),
                file_name=f"{table}.csv",
                mime="text/csv",
                key=f"export_{table}",
            )

render_section_title("ローカル高速スクレイピング", "更新機能はローカルCLI実行に統一しました。")
render_surface("この画面からの更新ボタンは廃止しました。以下のコマンドをローカル端末で実行してください。", tone="soft")
scrape_command = "\n".join(
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
with st.container(border=True):
    st.caption("実行コマンド（PowerShell）")
    st.code(scrape_command, language="powershell")
refresh_col, _ = st.columns([1, 4], gap="small")
with refresh_col:
    refresh_requested = st.button("実行履歴を再読み込み", key="reload_scrape_runs", use_container_width=True)
if refresh_requested:
    clear_scrape_cache()
    st.rerun()

render_section_title("最近の品種取得実行", "直近の取込ジョブ結果を確認できます。")
runs = get_recent_variety_scrape_runs()
success_count = sum(1 for row in runs if row.get("status") == "success")
failed_count = sum(1 for row in runs if row.get("status") == "failed")
latest_success = next((row.get("finished_at") for row in runs if row.get("status") == "success"), None)
render_kpi_cards(
    [
        ("直近表示件数", str(len(runs)), "最大表示件数"),
        ("成功件数", str(success_count), "表示範囲内"),
        ("失敗件数", str(failed_count), "表示範囲内"),
        ("最新成功時刻", latest_success or "-", "UTC時刻文字列"),
    ]
)
with st.container(border=True):
    if runs:
        st.dataframe(runs, use_container_width=True, hide_index=True)
    else:
        render_empty_state(
            "表示できる取込実行履歴がありません。",
            title="実行履歴はまだありません",
            hint="ローカル端末で取込コマンドを実行後に再読み込みしてください。",
        )

render_section_title("取得ログ確認", "実行IDを選択すると詳細ログを確認できます。")
selected_run_id = ""
if runs:
    with st.container(border=True):
        selected_run_id = st.selectbox(
            "ログを確認する実行ID",
            [""] + [r["id"] for r in runs],
            format_func=lambda x: "選択してください" if not x else x,
        )
    if selected_run_id:
        logs = get_variety_scrape_logs(selected_run_id, limit=200)
        with st.container(border=True):
            if logs:
                st.dataframe(logs, use_container_width=True, hide_index=True)
            else:
                render_empty_state("この実行IDに紐づくログはありません。", title="表示できるログがありません")
else:
    render_empty_state(
        "実行IDがないためログを選択できません。",
        title="ログの表示対象がありません",
        hint="まずローカル取込を実行してから履歴を再読み込みしてください。",
    )

render_section_title("診断情報", "現在の運用設定と接続前提条件を確認します。")
render_surface("定期的に接続キー状態と最終成功時刻を確認し、運用停止を早期に検知してください。", tone="soft")
auth_persistence = get_auth_persistence_status()
if auth_persistence["code"] in {"ready_ephemeral_secret", "cookie_manager_not_ready_ephemeral_secret", "missing_secret"}:
    st.warning(auth_persistence["message"])
elif not auth_persistence["available"]:
    st.info(auth_persistence["message"])
diagnostic_snapshot = {
    "app_version": "v3.0.0",
    "timezone": cfg.app_timezone,
    "has_supabase_url": bool(cfg.supabase_url),
    "has_supabase_anon_key": bool(cfg.supabase_anon_key),
    "auth_persistence_available": auth_persistence["available"],
    "auth_persistence_code": auth_persistence["code"],
    "scrape_mode": "local_cli_only",
    "last_successful_variety_scrape": latest_success,
    "checked_at": datetime.utcnow().isoformat(),
}
with st.container(border=True):
    st.caption("システムスナップショット (JSON)")
    st.json(diagnostic_snapshot, expanded=False)
