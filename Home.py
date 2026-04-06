"""StrawberryLab home page."""

from __future__ import annotations

import streamlit as st

from src.components.sidebar import render_sidebar
from src.services.auth_service import initialize_auth_state, login_user

st.set_page_config(page_title="StrawberryLab", layout="wide")
initialize_auth_state()


def _render_login() -> None:
    st.title("StrawberryLab")
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
    st.title("ダッシュボード")
    c1, c2, c3, c4, c5 = st.columns(5)
    active_varieties = client.table("varieties").select("id", count="exact", head=True).is_("deleted_at", "null").execute().count or 0
    active_reviews = client.table("reviews").select("id", count="exact", head=True).is_("deleted_at", "null").execute().count or 0
    unread_articles = client.table("scraped_articles").select("id", count="exact", head=True).eq("is_read", False).execute().count or 0
    notes_count = client.table("notes").select("id", count="exact", head=True).is_("deleted_at", "null").execute().count or 0
    avg_overall = client.table("reviews").select("overall").is_("deleted_at", "null").execute().data or []
    avg_score = round(sum(x["overall"] for x in avg_overall) / len(avg_overall), 2) if avg_overall else 0
    c1.metric("有効品種数", active_varieties)
    c2.metric("有効レビュー数", active_reviews)
    c3.metric("未読記事数", unread_articles)
    c4.metric("ノート数", notes_count)
    c5.metric("平均総合評価", avg_score)
    run = client.table("scrape_runs").select("status,finished_at").order("started_at", desc=True).limit(1).execute().data or []
    st.caption(f"最新スクレイプ状態: {run[0]['status'] if run else '-'}")
    st.subheader("最新レビュー")
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
    st.subheader("最新未読記事")
    articles = (
        client.table("scraped_articles")
        .select("title,source_name,scraped_at")
        .eq("is_read", False)
        .order("scraped_at", desc=True)
        .limit(5)
        .execute()
        .data
        or []
    )
    st.dataframe(articles, use_container_width=True, hide_index=True)
    st.page_link("pages/01_varieties.py", label="品種管理へ")
    st.page_link("pages/02_reviews.py", label="試食評価へ")
    st.page_link("pages/03_analytics.py", label="分析へ")


if st.session_state.get("is_authenticated"):
    _render_dashboard()
else:
    _render_login()
