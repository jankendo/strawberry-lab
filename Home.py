"""StrawberryLab home page."""

from __future__ import annotations

import streamlit as st

from src.components.layout import (
    inject_app_style,
    render_info_card,
    render_kpi_cards,
    render_lead,
    render_page_header,
    render_section_title,
)
from src.components.sidebar import render_sidebar
from src.services.auth_service import initialize_auth_state, login_user

st.set_page_config(page_title="StrawberryLab", layout="wide")
initialize_auth_state()
inject_app_style()


def _render_login() -> None:
    render_page_header("StrawberryLab", "いちご品種の研究・評価を一元管理するための管理アプリです。")
    render_lead("品種登録情報・試食評価・分析・メモを一体運用する管理者向けワークスペースです。")
    with st.container():
        st.subheader("ログイン")
        with st.form("login_form"):
            email = st.text_input("メールアドレス")
            password = st.text_input("パスワード", type="password")
            submitted = st.form_submit_button("ログイン", use_container_width=True)
        if submitted:
            try:
                login_user(email, password)
                st.success("ログインしました。")
                st.rerun()
            except PermissionError as exc:
                st.error(str(exc))
            except Exception:
                st.error("ログインに失敗しました。")


def _render_dashboard() -> None:
    render_sidebar()
    client = st.session_state["supabase_client_user"]
    render_page_header("ダッシュボード", "主要指標と最新データを確認できます。")

    active_varieties = (
        client.table("varieties")
        .select("id", count="exact", head=True)
        .is_("deleted_at", "null")
        .execute()
        .count
        or 0
    )
    active_reviews = (
        client.table("reviews")
        .select("id", count="exact", head=True)
        .is_("deleted_at", "null")
        .execute()
        .count
        or 0
    )
    notes_count = (
        client.table("notes")
        .select("id", count="exact", head=True)
        .is_("deleted_at", "null")
        .execute()
        .count
        or 0
    )
    avg_overall = client.table("reviews").select("overall").is_("deleted_at", "null").execute().data or []
    avg_score = round(sum(x["overall"] for x in avg_overall) / len(avg_overall), 2) if avg_overall else 0
    latest_scrape = (
        client.table("variety_scrape_runs")
        .select("status,finished_at,upserted_count")
        .order("started_at", desc=True)
        .limit(1)
        .execute()
        .data
        or []
    )
    latest_status = latest_scrape[0]["status"] if latest_scrape else "-"
    latest_upserted = latest_scrape[0]["upserted_count"] if latest_scrape else 0

    render_kpi_cards(
        [
            ("有効品種数", str(active_varieties), None),
            ("有効レビュー数", str(active_reviews), None),
            ("研究メモ数", str(notes_count), None),
            ("直近取得件数", str(latest_upserted), f"状態: {latest_status}"),
            ("平均総合評価", f"{avg_score:.2f}", "10点満点"),
        ]
    )
    render_info_card(
        "運用ヒント: 新規取得後は <strong>品種管理</strong> で画像と説明を確認し、"
        "必要に応じて補足メモを追記してください。"
    )

    render_section_title("最新レビュー", "直近5件の試食評価を表示します。")
    reviews = (
        client.table("reviews")
        .select("tasted_date,overall,varieties(name)")
        .is_("deleted_at", "null")
        .order("tasted_date", desc=True)
        .limit(5)
        .execute()
        .data
        or []
    )
    st.dataframe(reviews, use_container_width=True, hide_index=True)

    render_section_title("最新品種取得ログ", "直近5件のMAFF品種取得結果を表示します。")
    recent_runs = (
        client.table("variety_scrape_runs")
        .select("started_at,finished_at,status,upserted_count,failed_count")
        .order("started_at", desc=True)
        .limit(5)
        .execute()
        .data
        or []
    )
    st.dataframe(recent_runs, use_container_width=True, hide_index=True)

    render_section_title("主要メニュー")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.page_link("pages/01_varieties.py", label="品種管理")
    c2.page_link("pages/02_reviews.py", label="試食評価")
    c3.page_link("pages/03_analytics.py", label="分析ダッシュボード")
    c4.page_link("pages/04_pedigree.py", label="交配図")
    c5.page_link("pages/06_notes.py", label="研究メモ")


if st.session_state.get("is_authenticated"):
    _render_dashboard()
else:
    _render_login()
