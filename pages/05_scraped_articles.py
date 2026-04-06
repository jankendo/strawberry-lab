"""Scraped articles page."""

from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

from src.components.pagination import render_pagination_controls
from src.components.sidebar import render_sidebar
from src.components.tables import render_table
from src.services.auth_service import require_admin_session
from src.services.scrape_service import bulk_mark_filtered_articles_read, list_articles, set_article_read_status
from src.services.variety_service import list_active_varieties

st.set_page_config(page_title="スクレイプ記事", layout="wide")
require_admin_session()
render_sidebar()
st.title("スクレイプ記事")

varieties = list_active_varieties()
col1, col2, col3, col4 = st.columns(4)
with col1:
    source = st.selectbox("ソース", ["", "maff", "naro", "ja_news"])
with col2:
    keyword = st.text_input("キーワード")
with col3:
    unread_only = st.checkbox("未読のみ", value=False)
with col4:
    related_variety = st.selectbox("関連品種", [""] + [v["id"] for v in varieties], format_func=lambda x: "すべて" if not x else next(v["name"] for v in varieties if v["id"] == x))
date_col1, date_col2 = st.columns(2)
with date_col1:
    date_from = st.date_input("取得日開始", value=date.today() - timedelta(days=365), key="articles_from")
with date_col2:
    date_to = st.date_input("取得日終了", value=date.today(), key="articles_to")
page, page_size = render_pagination_controls("articles")
rows, total = list_articles(source=source or None, keyword=keyword or None, unread_only=unread_only, related_variety_id=related_variety or None, date_from=date_from, date_to=date_to, page=page, page_size=page_size)
st.caption(f"合計: {total}件")
render_table(rows)

if st.button("現在フィルタ結果を一括既読"):
    count = bulk_mark_filtered_articles_read({"source": source or None, "keyword": keyword or None, "unread_only": unread_only, "related_variety_id": related_variety or None, "date_from": date_from, "date_to": date_to})
    st.success(f"{count}件を既読化しました。")
    st.rerun()

for row in rows:
    col_a, col_b, col_c = st.columns([6, 2, 2])
    col_a.markdown(f"**{row['title']}**  \n{row['summary'][:200]}")
    with col_b:
        new_status = not bool(row.get("is_read"))
        label = "未読に戻す" if row.get("is_read") else "既読にする"
        if st.button(label, key=f"toggle_{row['id']}"):
            set_article_read_status(row["id"], new_status)
            st.rerun()
    with col_c:
        st.link_button("記事を開く", row["article_url"])
