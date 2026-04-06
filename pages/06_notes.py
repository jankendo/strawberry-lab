"""Notes page."""

from __future__ import annotations

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
from src.components.pagination import render_pagination_controls
from src.components.sidebar import render_sidebar
from src.components.tables import render_table
from src.services.auth_service import require_admin_session
from src.services.note_service import create_note, list_notes, restore_note, soft_delete_note, update_note
from src.services.variety_service import list_active_varieties
from src.utils.text_utils import split_dedup_values

st.set_page_config(page_title="研究メモ", layout="wide")
require_admin_session()
inject_app_style()
render_sidebar(active_page="notes")
render_hero_banner(
    "研究メモ",
    "調査メモを一元管理し、検索・編集・復元までを同じワークフローで運用できます。",
    eyebrow="研究ナレッジ管理",
    chips=["横断検索", "下書きプレビュー", "削除復元"],
)
render_action_bar(
    title="運用の流れ",
    description="左でノートを探し、右でプレビュー/編集します。削除操作は選択中ノートのみ表示されます。",
    actions=["検索", "タグ絞り込み", "プレビュー", "保存/削除", "削除済み復元"],
)

tab_manage, tab_deleted = st.tabs(["ノート管理", "削除済み"])

with tab_manage:
    render_section_title("ノート一覧", "左で一覧、右でプレビュー/編集を行います。")
    with st.container(border=True):
        c1, c2, c3 = st.columns([2, 1.3, 1], gap="medium")
        with c1:
            search_query = st.text_input("検索（タイトル・本文・タグ）", key="notes_search_query")
        with c2:
            tag_query = st.text_input("タグ絞り込み（カンマ区切り）", key="notes_tag_query")
        with c3:
            sort_mode = st.selectbox("並び順", ["更新が新しい順", "更新が古い順", "タイトル順"], key="notes_sort_mode")
        page, page_size = render_pagination_controls("notes_list")

    rows, total = list_notes(search_query=search_query or None, page=page, page_size=page_size)
    filter_tags = {tag.strip() for tag in tag_query.split(",") if tag.strip()}
    if filter_tags:
        rows = [row for row in rows if filter_tags.issubset(set(row.get("tags") or []))]
    if sort_mode == "更新が古い順":
        rows = sorted(rows, key=lambda row: row.get("updated_at") or "")
    elif sort_mode == "タイトル順":
        rows = sorted(rows, key=lambda row: row.get("title") or "")
    else:
        rows = sorted(rows, key=lambda row: row.get("updated_at") or "", reverse=True)

    render_kpi_cards(
        [
            ("検索ヒット", f"{total}件", "条件一致"),
            ("表示件数", f"{len(rows)}件", f"ページ {page}"),
            ("1ページ表示", f"{page_size}件", "ページネーション"),
        ]
    )

    if "notes_selected_id" not in st.session_state:
        st.session_state["notes_selected_id"] = ""

    left_col, right_col = st.columns([1.3, 1], gap="large")
    with left_col:
        if st.button("＋ 新しいメモを作成", use_container_width=True, type="primary", key="notes_create_new"):
            st.session_state["notes_selected_id"] = ""
            st.rerun()

        if rows:
            for row in rows:
                with st.container(border=True):
                    st.markdown(f"**{row.get('title') or 'タイトル未設定'}**")
                    st.caption(f"更新: {row.get('updated_at') or '-'}")
                    tags_text = ", ".join(row.get("tags") or [])
                    if tags_text:
                        st.caption(f"タグ: {tags_text}")
                    body = row.get("body") or ""
                    snippet = body.replace("\n", " ")
                    if len(snippet) > 90:
                        snippet = f"{snippet[:90].rstrip()}…"
                    st.write(snippet or "本文なし")
                    if st.button("このノートを開く", key=f"open_note_{row['id']}", use_container_width=True):
                        st.session_state["notes_selected_id"] = row["id"]
                        st.rerun()
        else:
            render_empty_state(
                "条件に一致するノートがありません。",
                title="検索結果がありません",
                hint="キーワードやタグ条件を見直してください。",
            )

    with right_col:
        selected_id = st.session_state.get("notes_selected_id") or ""
        selected_note = next((row for row in rows if row.get("id") == selected_id), None)
        is_edit_mode = selected_note is not None
        varieties = list_active_varieties()
        variety_name_map = {v["id"]: v.get("name") or v["id"] for v in varieties}
        default_tags = ", ".join(selected_note.get("tags") or []) if selected_note else ""
        editor_token = selected_id if is_edit_mode else "new"

        with st.container(border=True):
            st.markdown("**ノート編集**" if is_edit_mode else "**ノート作成**")
            with st.form("note_editor_form"):
                title = st.text_input(
                    "タイトル*",
                    value=selected_note.get("title") if selected_note else "",
                    key=f"notes_editor_title_{editor_token}",
                )
                body = st.text_area(
                    "本文*",
                    value=selected_note.get("body") if selected_note else "",
                    height=260,
                    key=f"notes_editor_body_{editor_token}",
                )
                current_variety = selected_note.get("variety_id") if selected_note else ""
                variety_id = st.selectbox(
                    "関連品種（任意）",
                    [""] + [v["id"] for v in varieties],
                    index=([""] + [v["id"] for v in varieties]).index(current_variety) if current_variety in variety_name_map else 0,
                    format_func=lambda x: "なし" if not x else variety_name_map.get(x, x),
                    key=f"notes_editor_variety_{editor_token}",
                )
                tags_raw = st.text_input("タグ（カンマ区切り）", value=default_tags, key=f"notes_editor_tags_{editor_token}")
                submitted = st.form_submit_button("保存", use_container_width=True, type="primary")

            with st.expander("プレビュー", expanded=False):
                if body:
                    st.markdown(body)
                else:
                    st.caption("本文を入力するとここにプレビューされます。")

            if submitted:
                try:
                    tags = split_dedup_values(tags_raw, max_items=20, max_length=30)
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    payload = {"title": title, "body": body, "variety_id": variety_id or None, "tags": tags}
                    try:
                        if is_edit_mode:
                            update_note(selected_id, payload)
                            st.success("更新しました。")
                        else:
                            new_note_id = create_note(payload)
                            st.session_state["notes_selected_id"] = new_note_id
                            st.success("作成しました。")
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))

            if is_edit_mode:
                if st.button("このノートを削除", key="notes_delete_selected", use_container_width=True, type="secondary"):
                    soft_delete_note(selected_id)
                    st.session_state["notes_selected_id"] = ""
                    st.success("削除しました。")
                    st.rerun()

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
