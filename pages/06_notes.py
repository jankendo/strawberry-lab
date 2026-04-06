"""Notes page."""

from __future__ import annotations

import streamlit as st

from src.components.forms import comma_values_input
from src.components.layout import inject_app_style, render_page_header, render_section_title
from src.components.pagination import render_pagination_controls
from src.components.sidebar import render_sidebar
from src.components.tables import render_table
from src.services.auth_service import require_admin_session
from src.services.note_service import create_note, list_notes, restore_note, soft_delete_note, update_note
from src.services.variety_service import list_active_varieties

st.set_page_config(page_title="研究メモ", layout="wide")
require_admin_session()
inject_app_style()
render_sidebar()
render_page_header("研究メモ", "ノートの検索・作成・編集・削除復元を行います。")

tab_list, tab_edit, tab_deleted = st.tabs(["一覧", "作成・編集", "削除済み"])

with tab_list:
    render_section_title("ノート一覧")
    search_query = st.text_input("検索（タイトル・本文・タグ）")
    page, page_size = render_pagination_controls("notes_list")
    rows, total = list_notes(search_query=search_query or None, page=page, page_size=page_size)
    st.caption(f"合計: {total}件")
    render_table(rows)
    delete_id = st.selectbox(
        "削除対象",
        [""] + [r["id"] for r in rows],
        format_func=lambda x: next((r["title"] for r in rows if r["id"] == x), "未選択"),
    )
    if delete_id and st.button("削除する"):
        soft_delete_note(delete_id)
        st.success("削除しました。")
        st.rerun()

with tab_edit:
    render_section_title("ノート作成・編集")
    varieties = list_active_varieties()
    note_id = st.text_input("編集対象ノートID（空欄で新規）")
    with st.form("note_form"):
        title = st.text_input("タイトル*")
        body = st.text_area("本文*", height=250)
        variety_id = st.selectbox(
            "関連品種（任意）",
            [""] + [v["id"] for v in varieties],
            format_func=lambda x: "なし" if not x else next(v["name"] for v in varieties if v["id"] == x),
        )
        tags = comma_values_input("タグ", "note_tags", 20, 30)
        submitted = st.form_submit_button("保存", use_container_width=True)
    with st.expander("プレビュー", expanded=False):
        st.markdown(body or "")
    if submitted:
        payload = {"title": title, "body": body, "variety_id": variety_id or None, "tags": tags}
        try:
            if note_id:
                update_note(note_id, payload)
                st.success("更新しました。")
            else:
                create_note(payload)
                st.success("作成しました。")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))

with tab_deleted:
    render_section_title("削除済みノート")
    page, page_size = render_pagination_controls("notes_deleted")
    rows, _ = list_notes(include_deleted=True, page=page, page_size=page_size)
    deleted_rows = [row for row in rows if row.get("deleted_at")]
    render_table(deleted_rows)
    restore_id = st.selectbox(
        "復元対象",
        [""] + [r["id"] for r in deleted_rows],
        format_func=lambda x: next((r["title"] for r in deleted_rows if r["id"] == x), "未選択"),
    )
    if restore_id and st.button("復元する", key="restore_note"):
        restore_note(restore_id)
        st.success("復元しました。")
        st.rerun()
