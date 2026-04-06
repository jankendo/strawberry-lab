"""Notes page."""

from __future__ import annotations

import streamlit as st

from src.components.forms import comma_values_input
from src.components.layout import (
    inject_app_style,
    render_action_bar,
    render_empty_state,
    render_hero_banner,
    render_kpi_cards,
    render_section_title,
    render_surface,
)
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
render_hero_banner(
    "研究メモ",
    "調査メモを一元管理し、検索・編集・復元までを同じワークフローで運用できます。",
    eyebrow="研究ナレッジ管理",
    chips=["横断検索", "下書きプレビュー", "削除復元"],
)
render_action_bar(
    title="運用の流れ",
    description="一覧で探し、作成・編集で更新し、不要なノートは削除済みタブから安全に復元できます。",
    actions=["キーワード検索", "タイトル/本文を保存", "タグを整理", "必要時に復元"],
)

tab_list, tab_edit, tab_deleted = st.tabs(["一覧", "作成・編集", "削除済み"])

with tab_list:
    render_section_title("ノート一覧", "タイトル・本文・タグを横断検索し、対象ノートをすばやく確認できます。")
    with st.container(border=True):
        filter_col, paging_col = st.columns([2, 1], gap="medium")
        with filter_col:
            search_query = st.text_input("検索（タイトル・本文・タグ）", key="notes_search_query")
        with paging_col:
            st.caption("ページ設定")
            page, page_size = render_pagination_controls("notes_list")
    rows, total = list_notes(search_query=search_query or None, page=page, page_size=page_size)
    render_kpi_cards(
        [
            ("検索ヒット", f"{total}件", "条件一致"),
            ("表示件数", f"{len(rows)}件", f"ページ {page}"),
            ("1ページ表示", f"{page_size}件", "ページネーション"),
        ]
    )
    with st.container(border=True):
        if rows:
            render_table(rows)
        else:
            render_empty_state(
                "条件に一致するノートがありません。",
                title="検索結果がありません",
                hint="キーワードを変更して再検索してください。",
            )
    render_surface("削除しても「削除済み」タブから復元できます。運用中の誤削除に備えて確認してから実行してください。", tone="soft")
    with st.container(border=True):
        st.caption("削除操作")
        delete_select_col, delete_action_col = st.columns([3, 1], gap="small")
        with delete_select_col:
            delete_id = st.selectbox(
                "削除対象",
                [""] + [r["id"] for r in rows],
                key="notes_delete_target",
                format_func=lambda x: next((r["title"] for r in rows if r["id"] == x), "未選択"),
            )
        with delete_action_col:
            delete_requested = st.button(
                "選択したノートを削除",
                key="notes_delete_submit",
                use_container_width=True,
                disabled=not delete_id,
            )
    if delete_id and delete_requested:
        soft_delete_note(delete_id)
        st.success("削除しました。")
        st.rerun()

with tab_edit:
    render_section_title("ノート作成・編集", "空欄なら新規作成、ノートID入力時は既存ノートを更新します。")
    render_action_bar(
        title="入力ガイド",
        description="タイトルと本文は必須です。タグはカンマ区切りで入力し、保存前にプレビューで内容を確認できます。",
        actions=["タイトル必須", "本文必須", "タグはカンマ区切り", "保存後に再読み込み"],
    )
    varieties = list_active_varieties()
    note_id = st.text_input("編集対象ノートID（空欄で新規）", key="notes_edit_target_id")
    form_col, preview_col = st.columns([3, 2], gap="large")
    with form_col:
        with st.container(border=True):
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
    with preview_col:
        with st.container(border=True):
            with st.expander("プレビュー", expanded=False):
                if body:
                    st.markdown(body)
                else:
                    st.caption("本文を入力するとここにプレビューされます。")
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
    render_section_title("削除済みノート", "削除済みノートの一覧確認と復元操作を行います。")
    with st.container(border=True):
        st.caption("ページ設定")
        page, page_size = render_pagination_controls("notes_deleted")
    rows, _ = list_notes(include_deleted=True, page=page, page_size=page_size)
    deleted_rows = [row for row in rows if row.get("deleted_at")]
    render_kpi_cards(
        [
            ("削除済み件数", f"{len(deleted_rows)}件", "現在ページ"),
            ("1ページ表示", f"{page_size}件", f"ページ {page}"),
        ]
    )
    with st.container(border=True):
        if deleted_rows:
            render_table(deleted_rows)
        else:
            render_empty_state("削除済みノートはありません。", title="復元対象がありません")
    render_surface("復元したノートは通常の一覧タブで再編集できます。", tone="soft")
    with st.container(border=True):
        st.caption("復元操作")
        restore_select_col, restore_action_col = st.columns([3, 1], gap="small")
        with restore_select_col:
            restore_id = st.selectbox(
                "復元対象",
                [""] + [r["id"] for r in deleted_rows],
                key="notes_restore_target",
                format_func=lambda x: next((r["title"] for r in deleted_rows if r["id"] == x), "未選択"),
            )
        with restore_action_col:
            restore_requested = st.button(
                "選択したノートを復元",
                key="restore_note",
                use_container_width=True,
                disabled=not restore_id,
            )
    if restore_id and restore_requested:
        restore_note(restore_id)
        st.success("復元しました。")
        st.rerun()
