"""Notes page."""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from src.components.draft_buffer import clear_draft_buffer, render_draft_buffer_bridge
from src.components.layout import (
    inject_app_style,
    render_action_bar,
    render_empty_state,
    render_hero_banner,
    render_kpi_cards,
    render_page_header,
    render_section_title,
    render_sticky_primary_action_anchor,
)
from src.components.pagination import render_pagination_controls
from src.components.sidebar import render_primary_nav, render_sidebar
from src.components.skeletons import render_card_skeleton, render_list_skeleton, render_table_skeleton
from src.components.tables import is_mobile_client, render_table
from src.components.transitions import render_view_transition_layer, render_view_transition_trigger
from src.services.auth_service import require_admin_session
from src.services.note_service import create_note, get_note_detail, list_notes, restore_note, soft_delete_note, update_note
from src.services.variety_service import list_active_varieties
from src.utils.text_utils import split_dedup_values

_NOTES_SORT_OPTIONS = ["更新が新しい順", "更新が古い順", "タイトル順"]
_NOTES_SECTION_ORDER = ["ノート管理", "削除済み"]
_NOTES_PENDING_DRAFT_CLEARS_KEY = "notes_pending_draft_clears"
_NOTES_DRAFT_DISCARD_NOTICE_KEY = "notes_draft_discard_notice_key"
_NOTE_EDITOR_DRAFT_FIELDS = [
    {"name": "title", "label": "タイトル*", "kind": "text"},
    {"name": "body", "label": "本文*", "kind": "textarea"},
    {"name": "variety_id", "label": "関連品種（任意）", "kind": "select"},
    {"name": "tags_raw", "label": "タグ（カンマ区切り）", "kind": "text"},
]
_NOTES_CLEARED_DRAFT_KEYS_THIS_RUN: set[str] = set()


def _format_updated_at(value: object) -> str:
    if value in {None, ""}:
        return "-"
    text = str(value)
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return text


def _build_excerpt(body: object, *, max_length: int = 120) -> str:
    text = " ".join(str(body or "").split())
    if not text:
        return "本文なし"
    if len(text) <= max_length:
        return text
    return f"{text[:max_length].rstrip()}…"


def _resolve_selected_note(selected_id: str, rows: list[dict] | None = None) -> dict | None:
    if not selected_id:
        return None
    selected_note = None
    if rows:
        selected_note = next((row for row in rows if row.get("id") == selected_id), None)
    if selected_note is None:
        selected_note = get_note_detail(selected_id)
    if selected_note and selected_note.get("deleted_at"):
        return None
    return selected_note


def _sort_note_rows(rows: list[dict], sort_mode: str) -> list[dict]:
    if sort_mode == "更新が古い順":
        return sorted(rows, key=lambda row: row.get("updated_at") or "")
    if sort_mode == "タイトル順":
        return sorted(rows, key=lambda row: str(row.get("title") or "").casefold())
    return sorted(rows, key=lambda row: row.get("updated_at") or "", reverse=True)


def _render_manage_filters(*, is_mobile: bool) -> tuple[str, list[str], str, int, int]:
    with st.container(border=True):
        if is_mobile:
            search_query = st.text_input("検索（タイトル・本文・タグ）", key="notes_search_query")
            tag_query = st.text_input("タグ絞り込み（カンマ区切り）", key="notes_tag_query")
            sort_mode = st.selectbox("並び順", _NOTES_SORT_OPTIONS, key="notes_sort_mode")
        else:
            c1, c2, c3 = st.columns([2, 1.3, 1], gap="medium")
            with c1:
                search_query = st.text_input("検索（タイトル・本文・タグ）", key="notes_search_query")
            with c2:
                tag_query = st.text_input("タグ絞り込み（カンマ区切り）", key="notes_tag_query")
            with c3:
                sort_mode = st.selectbox("並び順", _NOTES_SORT_OPTIONS, key="notes_sort_mode")
        page, page_size = render_pagination_controls("notes_list")

    try:
        filter_tags = split_dedup_values(tag_query, max_items=20, max_length=30)
    except ValueError as exc:
        st.error(str(exc))
        filter_tags = []

    filter_signature = (search_query.strip(), ",".join(filter_tags), sort_mode, page_size)
    if st.session_state.get("notes_list_filter_signature") != filter_signature:
        st.session_state["notes_list_filter_signature"] = filter_signature
        st.session_state["notes_list_page"] = 1
        st.session_state["notes_list_page_input"] = 1
        page = 1

    return search_query, filter_tags, sort_mode, page, page_size


def _render_notes_section_switcher(*, is_mobile: bool) -> str:
    default_section = str(st.session_state.get("notes_active_section") or _NOTES_SECTION_ORDER[0])
    if default_section not in _NOTES_SECTION_ORDER:
        default_section = _NOTES_SECTION_ORDER[0]
    with st.container(border=True):
        render_section_title("表示セクション", None if is_mobile else "必要なセクションのみ描画して表示速度を保ちます。")
        if is_mobile:
            active_section = st.selectbox(
                "表示セクション",
                _NOTES_SECTION_ORDER,
                index=_NOTES_SECTION_ORDER.index(default_section),
                key="notes_active_section",
            )
        else:
            active_section = st.radio(
                "表示セクション",
                _NOTES_SECTION_ORDER,
                index=_NOTES_SECTION_ORDER.index(default_section),
                horizontal=True,
                key="notes_active_section",
            )
    return active_section


def _load_note_rows(
    *,
    search_query: str,
    filter_tags: list[str],
    page: int,
    page_size: int,
    sort_mode: str,
) -> tuple[list[dict], int]:
    rows, total = list_notes(
        search_query=search_query or None,
        tags=filter_tags or None,
        page=page,
        page_size=page_size,
    )
    if not rows and total > 0 and page > 1:
        st.session_state["notes_list_page"] = 1
        st.session_state["notes_list_page_input"] = 1
        st.rerun()
    return _sort_note_rows(rows, sort_mode), total


def _render_notes_loading_skeleton(*, is_mobile: bool, mode: str) -> None:
    with st.container(border=True):
        if mode == "editor":
            st.caption("ノート詳細を読み込んでいます…")
            render_card_skeleton(count=1 if is_mobile else 2, is_mobile=is_mobile)
            render_list_skeleton(rows=2, is_mobile=is_mobile)
        else:
            st.caption("ノート一覧を取得しています…")
            render_table_skeleton(rows=4, columns=4, is_mobile=is_mobile)


def _render_create_note_action(*, is_mobile: bool) -> None:
    if is_mobile:
        render_sticky_primary_action_anchor("notes-create")
        render_view_transition_trigger("notes-mobile-list-detail", "list-to-detail")
    if st.button("＋ 新しいメモを作成", use_container_width=True, type="primary", key="notes_create_new"):
        st.session_state["notes_selected_id"] = ""
        st.session_state["notes_editor_mode"] = "create"
        if is_mobile:
            st.session_state["notes_mobile_view"] = "editor"
        st.rerun()


def _render_note_cards(rows: list[dict], *, is_mobile: bool) -> None:
    if not rows:
        render_empty_state(
            "条件に一致するノートがありません。",
            title="検索結果がありません",
            hint="キーワードやタグ条件を見直してください。",
        )
        return

    selected_id = st.session_state.get("notes_selected_id") or ""

    for row in rows:
        note_id = str(row.get("id") or "")
        with st.container(border=True):
            st.markdown(f"**{row.get('title') or 'タイトル未設定'}**")
            st.caption(f"更新: {_format_updated_at(row.get('updated_at'))}")
            tags = [str(tag).strip() for tag in (row.get("tags") or []) if str(tag).strip()]
            if tags:
                st.caption(f"タグ: {', '.join(tags)}")
            st.write(_build_excerpt(row.get("body")))
            if selected_id == note_id and not is_mobile:
                st.caption("現在選択中")
            if is_mobile:
                render_view_transition_trigger("notes-mobile-list-detail", "list-to-detail")
            if st.button("このノートを開く", key=f"open_note_{note_id}", use_container_width=True):
                st.session_state["notes_selected_id"] = note_id
                st.session_state["notes_editor_mode"] = "edit"
                if is_mobile:
                    st.session_state["notes_mobile_view"] = "editor"
                st.rerun()


def _note_editor_draft_key(editor_token: str) -> str:
    return f"notes-editor-{editor_token}"


def _queue_note_draft_clear(draft_key: str) -> None:
    pending_keys = [str(value) for value in st.session_state.get(_NOTES_PENDING_DRAFT_CLEARS_KEY, []) if str(value).strip()]
    if draft_key not in pending_keys:
        pending_keys.append(draft_key)
    st.session_state[_NOTES_PENDING_DRAFT_CLEARS_KEY] = pending_keys


def _render_note_editor(*, selected_id: str, selected_note: dict | None, is_mobile: bool) -> None:
    if is_mobile:
        render_view_transition_trigger("notes-mobile-list-detail", "detail-to-list")
    if is_mobile and st.button("← 一覧に戻る", key="notes_back_to_list", use_container_width=True):
        st.session_state["notes_mobile_view"] = "list"
        st.session_state["notes_editor_mode"] = "closed"
        st.rerun()

    is_edit_mode = selected_note is not None
    editor_loading_placeholder = st.empty()
    with editor_loading_placeholder.container():
        _render_notes_loading_skeleton(is_mobile=is_mobile, mode="editor")
    try:
        varieties = list_active_varieties()
    finally:
        editor_loading_placeholder.empty()

    variety_options = [""] + [v["id"] for v in varieties]
    variety_name_map = {v["id"]: v.get("name") or v["id"] for v in varieties}
    current_variety = selected_note.get("variety_id") if selected_note else ""
    default_tags = ", ".join(selected_note.get("tags") or []) if selected_note else ""
    editor_token = selected_id if is_edit_mode else "new"
    draft_key = _note_editor_draft_key(editor_token)
    clear_draft_before_restore = draft_key in _NOTES_CLEARED_DRAFT_KEYS_THIS_RUN

    with st.container(border=True):
        st.markdown("**ノート編集**" if is_edit_mode else "**ノート作成**")
        st.caption("入力内容はブラウザに自動保存されます。")
        if st.session_state.get(_NOTES_DRAFT_DISCARD_NOTICE_KEY) == draft_key:
            st.session_state.pop(_NOTES_DRAFT_DISCARD_NOTICE_KEY, None)
            st.caption("🗑️ 下書きを破棄しました。")
        with st.form("note_editor_form"):
            title = st.text_input(
                "タイトル*",
                value=selected_note.get("title") if selected_note else "",
                key=f"notes_editor_title_{editor_token}",
            )
            body = st.text_area(
                "本文*",
                value=selected_note.get("body") if selected_note else "",
                height=320 if is_mobile else 260,
                key=f"notes_editor_body_{editor_token}",
            )
            variety_id = st.selectbox(
                "関連品種（任意）",
                variety_options,
                index=variety_options.index(current_variety) if current_variety in variety_name_map else 0,
                format_func=lambda x: "なし" if not x else variety_name_map.get(x, x),
                key=f"notes_editor_variety_{editor_token}",
            )
            tags_raw = st.text_input("タグ（カンマ区切り）", value=default_tags, key=f"notes_editor_tags_{editor_token}")
            render_sticky_primary_action_anchor("notes-save")
            if is_mobile:
                render_view_transition_trigger("notes-mobile-list-detail", "detail-to-list")
            submitted = st.form_submit_button("保存", use_container_width=True, type="primary")

        with st.expander("プレビュー", expanded=False):
            if body:
                st.markdown(body)
            else:
                st.caption("本文を入力するとここにプレビューされます。")
        render_draft_buffer_bridge(
            draft_key,
            fields=_NOTE_EDITOR_DRAFT_FIELDS,
            notice_message="保存前のメモ下書きを復元しました。",
            clear_before_restore=clear_draft_before_restore,
        )
        discard_col, discard_hint_col = st.columns([1, 2], gap="small")
        with discard_col:
            discard_draft = st.button(
                "下書きを破棄",
                key=f"notes_discard_draft_{editor_token}",
                use_container_width=True,
                type="secondary",
            )
        with discard_hint_col:
            st.caption("ブラウザに保存された入力中の下書きを削除します。")

    if discard_draft:
        _queue_note_draft_clear(draft_key)
        st.session_state[_NOTES_DRAFT_DISCARD_NOTICE_KEY] = draft_key
        st.rerun()

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
                _queue_note_draft_clear(draft_key)
                if is_mobile:
                    st.session_state["notes_mobile_view"] = "list"
                    st.session_state["notes_editor_mode"] = "closed"
                else:
                    st.session_state["notes_editor_mode"] = "edit"
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

    if is_edit_mode:
        with st.expander("その他の操作", expanded=False):
            st.caption("削除後も「削除済み」タブから復元できます。")
            if is_mobile:
                render_view_transition_trigger("notes-mobile-list-detail", "detail-to-list")
            if st.button(
                "このノートを削除",
                key=f"notes_delete_selected_{editor_token}",
                use_container_width=True,
                type="secondary",
            ):
                soft_delete_note(selected_id)
                st.session_state["notes_selected_id"] = ""
                st.session_state["notes_editor_mode"] = "closed"
                if is_mobile:
                    st.session_state["notes_mobile_view"] = "list"
                st.success("削除しました。")
                st.rerun()


st.set_page_config(page_title="研究メモ", layout="wide")
require_admin_session()
inject_app_style()
render_sidebar(active_page="notes")
render_primary_nav(active_page="notes")
mobile_client = is_mobile_client()
if mobile_client:
    render_page_header("研究メモ", "一覧から必要なノートを開き、編集や復元を行います。")
else:
    render_hero_banner(
        "研究メモ",
        "調査メモを一元管理し、検索・編集・復元までを同じワークフローで運用できます。",
        eyebrow="研究ナレッジ管理",
        chips=["横断検索", "モバイル編集", "削除復元"],
    )
    render_action_bar(
        title="運用の流れ",
        description="一覧カードで検索・絞り込み後にノートを開いて編集します。モバイルでは編集画面を単画面表示します。",
        actions=["検索", "タグ絞り込み", "カードで選択", "保存", "削除済み復元"],
    )

if "notes_selected_id" not in st.session_state:
    st.session_state["notes_selected_id"] = ""
if "notes_mobile_view" not in st.session_state:
    st.session_state["notes_mobile_view"] = "list"
if "notes_editor_mode" not in st.session_state:
    st.session_state["notes_editor_mode"] = "closed"
pending_note_draft_clears = [str(value) for value in st.session_state.pop(_NOTES_PENDING_DRAFT_CLEARS_KEY, []) if str(value).strip()]
_NOTES_CLEARED_DRAFT_KEYS_THIS_RUN = set(pending_note_draft_clears)
for pending_draft_key in pending_note_draft_clears:
    clear_draft_buffer(pending_draft_key)
if mobile_client:
    render_view_transition_layer(
        "notes-mobile-list-detail",
        current_state=str(st.session_state.get("notes_mobile_view") or "list"),
        enabled=True,
        mobile_only=True,
    )

active_section = _render_notes_section_switcher(is_mobile=mobile_client)

if active_section == "ノート管理":
    render_section_title("ノート一覧", None if mobile_client else "検索・タグ絞り込みで探し、カードから開いて編集します。")
    if mobile_client and st.session_state.get("notes_mobile_view") == "editor":
        selected_id = st.session_state.get("notes_selected_id") or ""
        selected_note_loading_placeholder = st.empty()
        with selected_note_loading_placeholder.container():
            _render_notes_loading_skeleton(is_mobile=True, mode="editor")
        try:
            selected_note = _resolve_selected_note(selected_id)
        finally:
            selected_note_loading_placeholder.empty()
        if selected_id and selected_note is None:
            st.session_state["notes_selected_id"] = ""
            st.session_state["notes_mobile_view"] = "list"
            st.session_state["notes_editor_mode"] = "closed"
            st.rerun()
        _render_note_editor(selected_id=selected_id, selected_note=selected_note, is_mobile=True)
    else:
        search_query, filter_tags, sort_mode, page, page_size = _render_manage_filters(is_mobile=mobile_client)
        list_loading_placeholder = st.empty()
        with list_loading_placeholder.container():
            _render_notes_loading_skeleton(is_mobile=mobile_client, mode="list")
        try:
            rows, total = _load_note_rows(
                search_query=search_query,
                filter_tags=filter_tags,
                page=page,
                page_size=page_size,
                sort_mode=sort_mode,
            )
        finally:
            list_loading_placeholder.empty()
        render_kpi_cards(
            [
                ("検索ヒット", f"{total}件", "条件一致"),
                ("表示件数", f"{len(rows)}件", f"ページ {page}"),
                ("1ページ表示", f"{page_size}件", "ページネーション"),
            ]
        )

        if mobile_client:
            _render_create_note_action(is_mobile=True)
            _render_note_cards(rows, is_mobile=True)
        else:
            left_col, right_col = st.columns([1.3, 1], gap="large")
            with left_col:
                _render_create_note_action(is_mobile=False)
                _render_note_cards(rows, is_mobile=False)
            with right_col:
                editor_mode = str(st.session_state.get("notes_editor_mode") or "closed")
                selected_id = st.session_state.get("notes_selected_id") or ""
                if editor_mode == "edit" and selected_id:
                    selected_note_loading_placeholder = st.empty()
                    with selected_note_loading_placeholder.container():
                        _render_notes_loading_skeleton(is_mobile=False, mode="editor")
                    try:
                        selected_note = _resolve_selected_note(selected_id, rows)
                    finally:
                        selected_note_loading_placeholder.empty()
                    if selected_note is None:
                        st.session_state["notes_selected_id"] = ""
                        st.session_state["notes_editor_mode"] = "closed"
                        render_empty_state(
                            "一覧からノートを選択すると編集画面を表示します。",
                            title="ノート未選択",
                            hint="右側の編集フォームは必要なときだけ読み込みます。",
                        )
                    else:
                        _render_note_editor(selected_id=selected_id, selected_note=selected_note, is_mobile=False)
                elif editor_mode == "create":
                    _render_note_editor(selected_id="", selected_note=None, is_mobile=False)
                else:
                    render_empty_state(
                        "新しいメモを作成するか、一覧からノートを選択してください。",
                        title="編集フォームは未表示です",
                        hint="不要なフォーム描画を避けるため、初期表示では一覧のみ表示します。",
                    )

elif active_section == "削除済み":
    render_section_title("削除済みノート", "削除済みノートの一覧確認と復元操作を行います。")
    with st.container(border=True):
        st.caption("ページ設定")
        page, page_size = render_pagination_controls("notes_deleted")
    deleted_loading_placeholder = st.empty()
    with deleted_loading_placeholder.container():
        _render_notes_loading_skeleton(is_mobile=mobile_client, mode="list")
    try:
        rows, _ = list_notes(include_deleted=True, page=page, page_size=page_size)
    finally:
        deleted_loading_placeholder.empty()
    deleted_rows = [row for row in rows if row.get("deleted_at")]
    render_kpi_cards(
        [
            ("削除済み件数", f"{len(deleted_rows)}件", "現在ページ"),
            ("1ページ表示", f"{page_size}件", f"ページ {page}"),
        ]
    )
    with st.container(border=True):
        if deleted_rows:
            render_table(
                deleted_rows,
                mobile_title_key="title",
                mobile_subtitle_key="deleted_at",
                mobile_metadata_keys=["updated_at", "tags"],
            )
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
