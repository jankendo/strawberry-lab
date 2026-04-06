"""StrawberryLab home page."""

from __future__ import annotations

import streamlit as st

from src.components.layout import inject_app_style, render_page_header, render_section_title
from src.components.sidebar import render_sidebar
from src.services.auth_service import get_user_client, initialize_auth_state, login_user, restore_login_from_cookie

try:
    from src.components.layout import render_info_card, render_kpi_cards, render_lead
except ImportError:
    def render_lead(text: str) -> None:
        """Fallback lead renderer for partially refreshed runtimes."""
        st.caption(text)


    def render_info_card(text: str) -> None:
        """Fallback info card renderer for partially refreshed runtimes."""
        plain = text.replace("<strong>", "").replace("</strong>", "").replace("<br>", " ")
        st.info(plain)


    def render_kpi_cards(items: list[tuple[str, str, str | None]]) -> None:
        """Fallback KPI renderer for partially refreshed runtimes."""
        columns = st.columns(len(items))
        for column, (label, value, sub_text) in zip(columns, items, strict=True):
            column.metric(label, value, help=sub_text)

st.set_page_config(page_title="StrawberryLab", layout="wide")
initialize_auth_state()
restore_login_from_cookie()
inject_app_style()


@st.cache_data(ttl=120)
def _load_dashboard_metrics() -> dict:
    client = get_user_client()
    if client is None:
        return {"active_varieties": 0, "active_reviews": 0, "notes_count": 0, "avg_score": 0.0, "latest_status": "-", "latest_upserted": 0}

    active_varieties = (
        client.table("varieties").select("id", count="exact", head=True).is_("deleted_at", "null").execute().count or 0
    )
    active_reviews = (
        client.table("reviews").select("id", count="exact", head=True).is_("deleted_at", "null").execute().count or 0
    )
    notes_count = client.table("notes").select("id", count="exact", head=True).is_("deleted_at", "null").execute().count or 0
    overall_rows = client.table("reviews").select("overall").is_("deleted_at", "null").execute().data or []
    avg_score = round(sum(row["overall"] for row in overall_rows) / len(overall_rows), 2) if overall_rows else 0
    latest_scrape = (
        client.table("variety_scrape_runs")
        .select("status,upserted_count")
        .order("started_at", desc=True)
        .limit(1)
        .execute()
        .data
        or []
    )
    return {
        "active_varieties": int(active_varieties),
        "active_reviews": int(active_reviews),
        "notes_count": int(notes_count),
        "avg_score": float(avg_score),
        "latest_status": latest_scrape[0]["status"] if latest_scrape else "-",
        "latest_upserted": int(latest_scrape[0]["upserted_count"]) if latest_scrape else 0,
    }


@st.cache_data(ttl=120)
def _load_latest_reviews() -> list[dict]:
    client = get_user_client()
    if client is None:
        return []
    return (
        client.table("reviews")
        .select("tasted_date,overall,varieties(name)")
        .is_("deleted_at", "null")
        .order("tasted_date", desc=True)
        .limit(5)
        .execute()
        .data
        or []
    )


@st.cache_data(ttl=120)
def _load_recent_scrape_runs() -> list[dict]:
    client = get_user_client()
    if client is None:
        return []
    return (
        client.table("variety_scrape_runs")
        .select("started_at,finished_at,status,upserted_count,failed_count")
        .order("started_at", desc=True)
        .limit(5)
        .execute()
        .data
        or []
    )


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
    render_page_header("ダッシュボード", "主要指標と最新データを確認できます。")
    metrics = _load_dashboard_metrics()

    render_kpi_cards(
        [
            ("有効品種数", str(metrics["active_varieties"]), None),
            ("有効レビュー数", str(metrics["active_reviews"]), None),
            ("研究メモ数", str(metrics["notes_count"]), None),
            ("直近取得件数", str(metrics["latest_upserted"]), f"状態: {metrics['latest_status']}"),
            ("平均総合評価", f"{metrics['avg_score']:.2f}", "10点満点"),
        ]
    )
    render_info_card(
        "運用ヒント: 新規取得後は <strong>品種管理</strong> で画像と説明を確認し、"
        "必要に応じて補足メモを追記してください。"
    )

    render_section_title("最新レビュー", "直近5件の試食評価を表示します。")
    reviews = _load_latest_reviews()
    st.dataframe(reviews, use_container_width=True, hide_index=True)

    render_section_title("最新品種取得ログ", "直近5件のMAFF品種取得結果を表示します。")
    recent_runs = _load_recent_scrape_runs()
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
