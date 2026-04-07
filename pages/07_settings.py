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
    render_page_header,
    render_section_title,
    render_section_switcher,
    render_status_badge,
    render_surface,
)
from src.components.sidebar import render_primary_nav, render_sidebar
from src.components.tables import is_mobile_client, render_table
from src.config import get_config
from src.services.auth_service import get_auth_persistence_status, get_user_client, require_admin_session
from src.services.cache_service import get_cache_runtime_status
from src.services.export_service import export_table_csv
from src.services.scrape_service import (
    clear_scrape_cache,
    get_recent_variety_scrape_runs,
    get_variety_scrape_logs,
)

SECTION_ORDER = ["データ出力", "実行履歴", "ローカル実行", "診断情報"]
TABLE_ACCESS_CHECKS = [
    "app_users",
    "varieties",
    "variety_parent_links",
    "reviews",
    "variety_images",
    "review_images",
    "notes",
    "variety_scrape_runs",
    "variety_scrape_logs",
]


@st.cache_data(ttl=60)
def _get_table_access_diagnostics() -> list[dict[str, str]]:
    client = get_user_client()
    rows: list[dict[str, str]] = []
    for table_name in TABLE_ACCESS_CHECKS:
        try:
            response = client.table(table_name).select("*", count="exact").limit(1).execute()
            rows.append(
                {
                    "テーブル": table_name,
                    "状態": "OK",
                    "件数": str(int(response.count or 0)),
                    "詳細": "読込可",
                }
            )
        except Exception as exc:
            rows.append(
                {
                    "テーブル": table_name,
                    "状態": "NG",
                    "件数": "-",
                    "詳細": f"{type(exc).__name__}: {exc}",
                }
            )
    return rows
SECTION_HINTS = {
    "データ出力": "バックアップ・共有用のCSVを取得します。",
    "実行履歴": "取得ジョブの状態とログを確認します。",
    "ローカル実行": "ローカルCLIでの実行手順を確認します。",
    "診断情報": "接続状態と運用前提を点検します。",
}
_DEFAULT_ACTIVE_SECTION = "実行履歴"
_SETTINGS_ACTIVE_SECTION_KEY = "settings_active_section"
_STATUS_LABELS = {
    "success": "成功",
    "succeeded": "成功",
    "completed": "成功",
    "done": "成功",
    "running": "実行中",
    "in_progress": "実行中",
    "queued": "待機中",
    "pending": "待機中",
    "warning": "注意",
    "partial": "一部成功",
    "failed": "失敗",
    "error": "エラー",
    "cancelled": "キャンセル",
    "canceled": "キャンセル",
}
_SUCCESS_STATUSES = {"success", "succeeded", "completed", "done"}
_FAILED_STATUSES = {"failed", "error", "cancelled", "canceled"}


def _status_badge_theme(status: object | None) -> tuple[str, str]:
    normalized = str(status or "").strip().lower()
    if normalized in {"success", "succeeded", "completed", "done"}:
        return "success", "✅"
    if normalized in {"running", "in_progress", "queued", "pending"}:
        return "info", "⏳"
    if normalized in {"partial", "warning"}:
        return "warning", "⚠️"
    if normalized in {"failed", "error", "cancelled", "canceled"}:
        return "danger", "❗"
    return "neutral", "ℹ️"


def _status_label(status: object | None) -> str:
    normalized = str(status or "").strip().lower()
    if not normalized:
        return "-"
    return _STATUS_LABELS.get(normalized, str(status))


def _truncate_text(value: object | None, *, limit: int = 96) -> str:
    text = str(value or "").strip()
    if not text:
        return "-"
    return text if len(text) <= limit else f"{text[:limit - 1]}…"


def _safe_text(value: object | None) -> str:
    text = str(value or "").strip()
    return text or "-"


def _render_section_switcher(*, is_mobile: bool) -> str:
    _ = is_mobile
    active_section = render_section_switcher(
        SECTION_ORDER,
        key=_SETTINGS_ACTIVE_SECTION_KEY,
        title="設定セクション",
        description=None,
        mobile_label="表示セクション",
    )
    return active_section


st.set_page_config(page_title="設定", layout="wide")
require_admin_session()
inject_app_style()
render_sidebar(active_page="settings")
render_primary_nav(active_page="settings")
cfg = get_config()
mobile_client = is_mobile_client()

render_page_header(
    "設定",
    "データ出力・実行履歴・診断確認を目的別に切り替えて操作できます。"
    if not mobile_client
    else "必要なセクションを選んで操作できます。",
)
with st.container(border=True):
    if mobile_client:
        render_section_title("関連ページ")
        with st.expander("移動メニューを開く", expanded=False):
            st.page_link("pages/04_pedigree.py", label="🧬 交配図を開く", use_container_width=True)
    else:
        render_section_title("関連ページ")
        st.page_link("pages/04_pedigree.py", label="🧬 交配図を開く", use_container_width=True)

table_labels = {
    "varieties": "品種マスタ",
    "variety_parent_links": "親子リンク",
    "reviews": "試食レビュー",
    "variety_scrape_runs": "品種取得実行履歴",
    "variety_scrape_logs": "品種取得ログ",
}
export_tables = [
    "varieties",
    "variety_parent_links",
    "reviews",
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

active_section = _render_section_switcher(is_mobile=mobile_client)
runs: list[dict] = []
if active_section in {"実行履歴", "診断情報"}:
    runs = get_recent_variety_scrape_runs()

success_count = sum(1 for row in runs if str(row.get("status") or "").strip().lower() in _SUCCESS_STATUSES)
failed_count = sum(1 for row in runs if str(row.get("status") or "").strip().lower() in _FAILED_STATUSES)
latest_success = next(
    (
        row.get("finished_at")
        for row in runs
        if str(row.get("status") or "").strip().lower() in _SUCCESS_STATUSES
    ),
    None,
)

if active_section == "データ出力":
    render_section_title("データエクスポート")
    if st.button("CSVデータを読み込む", key="settings_load_exports", use_container_width=True, type="primary"):
        st.session_state["settings_exports_loaded"] = True
    if st.session_state.get("settings_exports_loaded"):
        export_payloads = {table: export_table_csv(table) for table in export_tables}
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zip_file:
            for table in export_tables:
                zip_file.writestr(f"{table}.csv", export_payloads[table])
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

        export_column_count = 1 if mobile_client else 2
        export_columns = st.columns(export_column_count, gap="small")
        for index, table in enumerate(export_tables):
            with export_columns[index % export_column_count]:
                with st.container(border=True):
                    st.markdown(f"**`{table}`（{table_labels.get(table, table)}）**")
                    st.download_button(
                        f"{table_labels.get(table, table)}をCSVダウンロード",
                        data=export_payloads[table],
                        file_name=f"{table}.csv",
                        mime="text/csv",
                        key=f"export_{table}",
                        use_container_width=True,
                    )
    else:
        st.caption("必要なときだけCSVを読み込みます。")

elif active_section == "実行履歴":
    if st.button("実行履歴を再読み込み", key="reload_scrape_runs", use_container_width=True, type="secondary"):
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
        run_rows: list[dict[str, object]] = []
        run_index: dict[str, dict] = {}
        for run in runs:
            run_id = _safe_text(run.get("id"))
            if run_id != "-":
                run_index[run_id] = run
            run_rows.append(
                {
                    "id": run_id,
                    "status": run.get("status"),
                    "started_at": run.get("started_at"),
                    "finished_at": run.get("finished_at"),
                    "upserted_count": run.get("upserted_count"),
                    "failed_count": run.get("failed_count"),
                    "processed_count": run.get("processed_count"),
                    "listed_count": run.get("listed_count"),
                }
            )

        selected_run_from_card = render_table(
            run_rows,
            mobile_title_key="status",
            mobile_subtitle_key="started_at",
            mobile_metadata_keys=["finished_at", "upserted_count", "failed_count", "processed_count"],
            mobile_tap_action_label="この実行IDのログを表示",
            mobile_tap_action_state_key="settings_selected_run_id",
            mobile_tap_action_value_key="id",
        )
        if selected_run_from_card is not None:
            st.session_state["settings_selected_run_id"] = str(selected_run_from_card)

        run_id_options = [""] + list(run_index.keys())
        selected_run_id_state = str(st.session_state.get("settings_selected_run_id", "") or "")
        if selected_run_id_state not in run_id_options:
            selected_run_id_state = ""
        selected_run_id = st.selectbox(
            "ログを確認する実行ID",
            run_id_options,
            index=run_id_options.index(selected_run_id_state),
            format_func=lambda value: "選択してください" if not value else value,
            key="settings_selected_run_id",
        )

        if selected_run_id:
            selected_run = run_index.get(selected_run_id)
            if selected_run:
                status_tone, status_icon = _status_badge_theme(selected_run.get("status"))
                with st.container(border=True):
                    render_status_badge(
                        f"実行ID {selected_run_id} / {_status_label(selected_run.get('status'))}",
                        tone=status_tone,
                        icon=status_icon,
                    )
                    st.caption(
                        f"開始: {_safe_text(selected_run.get('started_at'))} / "
                        f"終了: {_safe_text(selected_run.get('finished_at'))}"
                    )
                    st.caption(
                        f"反映: {selected_run.get('upserted_count') or 0} 件 / "
                        f"失敗: {selected_run.get('failed_count') or 0} 件 / "
                        f"処理: {selected_run.get('processed_count') or 0} 件"
                    )

            show_logs = st.toggle(
                "ログ詳細を読み込む",
                value=False,
                key=f"settings_load_logs_{selected_run_id}",
            )
            if show_logs:
                log_limit = int(
                    st.select_slider(
                        "ログ表示件数",
                        options=[50, 100, 150, 200],
                        value=100,
                        key=f"settings_log_limit_{selected_run_id}",
                    )
                )
                logs = get_variety_scrape_logs(selected_run_id, limit=log_limit)
                if logs:
                    compact_logs = [
                        {
                            "status": log.get("status"),
                            "created_at": log.get("created_at"),
                            "variety_name": log.get("variety_name"),
                            "error_message": _truncate_text(log.get("error_message")),
                            "detail_url": log.get("detail_url"),
                        }
                        for log in logs
                    ]
                    render_table(
                        compact_logs,
                        mobile_title_key="status",
                        mobile_subtitle_key="created_at",
                        mobile_metadata_keys=["variety_name", "error_message", "detail_url"],
                    )
                    if st.toggle(
                        "長文ログJSONを表示",
                        value=False,
                        key=f"settings_show_raw_logs_{selected_run_id}",
                    ):
                        with st.container(border=True):
                            st.caption("品種取得ログ（JSON）")
                            st.json(logs, expanded=False)
                else:
                    render_empty_state("この実行IDに紐づくログはありません。", title="表示できるログがありません")
            else:
                st.caption("必要なときだけログ詳細を読み込みます。")
    else:
        render_empty_state(
            "表示できる取込実行履歴がありません。",
            title="実行履歴はまだありません",
            hint="ローカル端末で取込コマンドを実行後に再読み込みしてください。",
        )

elif active_section == "ローカル実行":
    render_section_title("ローカル高速スクレイピング")
    st.caption("必要なときだけコマンドを展開してコピーしてください。")
    with st.expander("実行コマンド（PowerShell）", expanded=False):
        st.code(scrape_command, language="powershell")
    st.caption("実行後は「実行履歴」で状態を確認してください。")

elif active_section == "診断情報":
    render_section_title("診断情報")
    auth_persistence = get_auth_persistence_status()
    cache_runtime = get_cache_runtime_status()
    if auth_persistence["code"] == "public_access":
        st.success(auth_persistence["message"])
    elif not auth_persistence["available"]:
        st.warning(auth_persistence["message"])
    else:
        st.info(auth_persistence["message"])
    if cache_runtime["mode"] == "local" and cache_runtime["sticky_sessions_expected"]:
        st.info(str(cache_runtime["summary"]))

    with st.container(border=True):
        render_section_title("主要ステータス")
        render_status_badge(
            "SUPABASE_URL 設定済み" if cfg.supabase_url else "SUPABASE_URL 未設定",
            tone="success" if cfg.supabase_url else "danger",
            icon="🔗",
        )
        render_status_badge(
            "SUPABASE_ANON_KEY 設定済み" if cfg.supabase_anon_key else "SUPABASE_ANON_KEY 未設定",
            tone="success" if cfg.supabase_anon_key else "warning",
            icon="🔐",
        )
        render_status_badge(
            "公開モード: 有効" if auth_persistence["available"] else "公開モード: 制限あり",
            tone="success" if auth_persistence["available"] else "warning",
            icon="🪪",
        )
        render_status_badge(
            f"最終成功時刻 {_safe_text(latest_success)}",
            tone="success" if latest_success else "neutral",
            icon="🕒",
        )
        render_status_badge(
            "キャッシュ同期: Redis" if cache_runtime["mode"] == "redis" else "キャッシュ同期: ローカルメモリ",
            tone="success" if cache_runtime["mode"] == "redis" else "warning",
            icon="🧠",
        )
        render_status_badge(
            "セッション固定を想定" if cache_runtime["sticky_sessions_expected"] else "セッション固定なしでも運用可",
            tone="warning" if cache_runtime["sticky_sessions_expected"] else "neutral",
            icon="🧭",
        )

    with st.container(border=True):
        render_section_title("全テーブル接続チェック")
        st.caption("現在の公開モード client で各テーブルを 1 件ずつ読めるかを確認します。")
        render_table(
            _get_table_access_diagnostics(),
            mobile_title_key="テーブル",
            mobile_subtitle_key="状態",
            mobile_metadata_keys=["件数", "詳細"],
        )

    if st.toggle("詳細スナップショット(JSON)を読み込む", value=False, key="settings_show_diagnostic_snapshot"):
        diagnostic_snapshot = {
            "app_version": "v3.0.0",
            "timezone": cfg.app_timezone,
            "has_supabase_url": bool(cfg.supabase_url),
            "has_supabase_anon_key": bool(cfg.supabase_anon_key),
            "auth_persistence_available": auth_persistence["available"],
            "auth_persistence_code": auth_persistence["code"],
            "cache_mode": cache_runtime["mode"],
            "cache_redis_configured": cache_runtime["redis_configured"],
            "cache_redis_active": cache_runtime["redis_active"],
            "sticky_sessions_expected": cache_runtime["sticky_sessions_expected"],
            "scrape_mode": "local_cli_only",
            "last_successful_variety_scrape": latest_success,
            "checked_at": datetime.utcnow().isoformat(),
        }
        with st.container(border=True):
            st.caption("システムスナップショット (JSON)")
            st.json(diagnostic_snapshot, expanded=False)
    else:
        st.caption("詳細JSONは必要なときだけ読み込みます。")
