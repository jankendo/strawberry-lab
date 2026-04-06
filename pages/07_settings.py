"""Settings page."""

from __future__ import annotations

import io
from datetime import datetime
import zipfile

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
from src.components.tables import render_table
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
render_sidebar(active_page="settings")
cfg = get_config()
render_hero_banner(
    "設定",
    "データエクスポート、ローカル取込運用、診断確認を一画面で管理します。",
    eyebrow="運用管理",
    chips=["CSVエクスポート", "取込履歴確認", "診断チェック"],
)
render_action_bar(
    title="設定メニュー",
    description="目的ごとにタブを分けています。必要な機能だけを選んで操作してください。",
    actions=["データ出力", "実行履歴", "ローカル実行", "診断情報"],
)

table_labels = {
    "varieties": "品種マスタ",
    "variety_parent_links": "親子リンク",
    "reviews": "試食レビュー",
    "notes": "研究メモ",
    "variety_scrape_runs": "品種取得実行履歴",
    "variety_scrape_logs": "品種取得ログ",
}
export_tables = [
    "varieties",
    "variety_parent_links",
    "reviews",
    "notes",
    "variety_scrape_runs",
    "variety_scrape_logs",
]
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
runs = get_recent_variety_scrape_runs()
success_count = sum(1 for row in runs if row.get("status") == "success")
failed_count = sum(1 for row in runs if row.get("status") == "failed")
latest_success = next((row.get("finished_at") for row in runs if row.get("status") == "success"), None)

tab_export, tab_runs, tab_local, tab_diagnostic = st.tabs(
    ["データ出力", "実行履歴", "ローカル実行", "診断情報"]
)

with tab_export:
    render_section_title("データエクスポート", "一括ダウンロードと個別ダウンロードを分けて提供します。")
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        for table in export_tables:
            zip_file.writestr(f"{table}.csv", export_table_csv(table))
    zip_buffer.seek(0)
    st.download_button(
        "全テーブルCSVを一括ダウンロード（ZIP）",
        data=zip_buffer.getvalue(),
        file_name="strawberrylab_exports.zip",
        mime="application/zip",
        type="primary",
        use_container_width=True,
        key="export_all_zip",
    )
    export_columns = st.columns(2, gap="small")
    for index, table in enumerate(export_tables):
        with export_columns[index % len(export_columns)]:
            with st.container(border=True):
                st.markdown(f"**`{table}`（{table_labels.get(table, table)}）**")
                st.download_button(
                    f"{table_labels.get(table, table)}をCSVダウンロード",
                    data=export_table_csv(table),
                    file_name=f"{table}.csv",
                    mime="text/csv",
                    key=f"export_{table}",
                    use_container_width=True,
                )

with tab_runs:
    reload_col, _ = st.columns([1, 3], gap="large")
    with reload_col:
        refresh_requested = st.button("実行履歴を再読み込み", key="reload_scrape_runs", use_container_width=True)
    if refresh_requested:
        clear_scrape_cache()
        st.rerun()

    render_kpi_cards(
        [
            ("直近表示件数", str(len(runs)), "最大表示件数"),
            ("成功件数", str(success_count), "表示範囲内"),
            ("失敗件数", str(failed_count), "表示範囲内"),
            ("最新成功時刻", latest_success or "-", "UTC時刻"),
        ]
    )
    if runs:
        run_rows = []
        for run in runs:
            run_rows.append(
                {
                    "id": run.get("id"),
                    "status": run.get("status"),
                    "started_at": run.get("started_at"),
                    "finished_at": run.get("finished_at"),
                    "upserted_count": run.get("upserted_count"),
                    "failed_count": run.get("failed_count"),
                    "processed_count": run.get("processed_count"),
                    "listed_count": run.get("listed_count"),
                }
            )
        render_table(run_rows)

        selected_run_id = st.selectbox(
            "ログを確認する実行ID",
            [""] + [r["id"] for r in runs],
            format_func=lambda x: "選択してください" if not x else x,
        )
        if selected_run_id:
            logs = get_variety_scrape_logs(selected_run_id, limit=200)
            if logs:
                render_table(logs)
            else:
                render_empty_state("この実行IDに紐づくログはありません。", title="表示できるログがありません")
    else:
        render_empty_state(
            "表示できる取込実行履歴がありません。",
            title="実行履歴はまだありません",
            hint="ローカル端末で取込コマンドを実行後に再読み込みしてください。",
        )

with tab_local:
    render_section_title("ローカル高速スクレイピング", "更新処理はローカルCLI実行のみをサポートします。")
    with st.expander("実行コマンド（PowerShell）", expanded=False):
        st.code(scrape_command, language="powershell")
    st.text_area("コピー用コマンド", scrape_command, height=220)
    render_surface(
        "コマンドの実行後は「実行履歴」タブで状態・件数・エラー詳細を確認してください。",
        tone="soft",
    )

with tab_diagnostic:
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
