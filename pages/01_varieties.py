"""Varieties management page."""

from __future__ import annotations

import streamlit as st

from src.components.forms import comma_values_input
from src.components.image_gallery import render_image_gallery
from src.components.pagination import render_pagination_controls
from src.components.sidebar import render_sidebar
from src.components.tables import render_table
from src.constants.enums import AcidityLevel
from src.constants.prefectures import PREFECTURES
from src.services.auth_service import require_admin_session
from src.services.storage_service import list_images_with_signed_urls, set_primary_variety_image, upload_variety_image
from src.services.variety_service import create_variety, get_variety_detail, list_active_varieties, list_varieties, restore_variety, soft_delete_variety, update_variety

st.set_page_config(page_title="品種管理", layout="wide")
require_admin_session()
render_sidebar()
st.title("品種管理")

tab_list, tab_edit, tab_deleted = st.tabs(["一覧", "作成・編集", "削除済み"])

with tab_list:
    keyword = st.text_input("キーワード", key="variety_keyword")
    prefecture = st.selectbox("都道府県", [""] + PREFECTURES, key="variety_pref_filter")
    page, page_size = render_pagination_controls("variety_list")
    rows, total = list_varieties(keyword=keyword, prefecture=prefecture or None, page=page, page_size=page_size)
    st.caption(f"合計: {total}件")
    render_table(rows)
    preselected = st.session_state.pop("selected_variety_id", "")
    options = [""] + [r["id"] for r in rows]
    selected_id = st.selectbox(
        "詳細表示する品種",
        options,
        index=options.index(preselected) if preselected in options else 0,
        format_func=lambda x: next((r["name"] for r in rows if r["id"] == x), ""),
    )
    if selected_id:
        detail = get_variety_detail(selected_id)
        st.json(detail)
        images = list_images_with_signed_urls("variety_images", "variety_id", selected_id)
        render_image_gallery(images, "variety")
        if st.button("この品種を削除", key=f"delete_variety_{selected_id}"):
            soft_delete_variety(selected_id)
            st.success("削除しました。")
            st.rerun()

with tab_edit:
    active = list_active_varieties()
    edit_id = st.selectbox("編集対象", ["新規作成"] + [v["id"] for v in active], format_func=lambda x: "新規作成" if x == "新規作成" else next((v["name"] for v in active if v["id"] == x), x))
    base = get_variety_detail(edit_id) if edit_id != "新規作成" else {}
    with st.form("variety_form"):
        name = st.text_input("品種名*", value=base.get("name", ""))
        alias_names = comma_values_input("別名 (カンマ区切り)", "alias_names_input", 20, 50)
        origin_prefecture = st.selectbox("都道府県", [""] + PREFECTURES, index=([""] + PREFECTURES).index(base.get("origin_prefecture", "")))
        developer = st.text_input("開発者", value=base.get("developer", ""))
        registered_year = st.number_input("登録年", min_value=1900, max_value=2100, value=int(base.get("registered_year") or 2024))
        description = st.text_area("説明", value=base.get("description", ""))
        skin_color = st.text_input("果皮色", value=base.get("skin_color", ""))
        flesh_color = st.text_input("果肉色", value=base.get("flesh_color", ""))
        brix_min = st.number_input("糖度下限", min_value=0.0, max_value=30.0, value=float(base.get("brix_min") or 0.0))
        brix_max = st.number_input("糖度上限", min_value=0.0, max_value=30.0, value=float(base.get("brix_max") or 0.0))
        acidity_level = st.selectbox("酸味", [x.value for x in AcidityLevel], index=[x.value for x in AcidityLevel].index(base.get("acidity_level", "unknown")))
        harvest_start_month = st.number_input("収穫開始月", min_value=1, max_value=12, value=int(base.get("harvest_start_month") or 1))
        harvest_end_month = st.number_input("収穫終了月", min_value=1, max_value=12, value=int(base.get("harvest_end_month") or 12))
        tags = comma_values_input("タグ (カンマ区切り)", "variety_tags_input", 20, 30)
        parent_ids = st.multiselect("親品種", options=[v["id"] for v in active if v["id"] != edit_id], format_func=lambda i: next((v["name"] for v in active if v["id"] == i), i))
        uploaded_files = st.file_uploader("画像アップロード (最大5枚)", type=["jpg", "jpeg", "png", "webp"], accept_multiple_files=True)
        save = st.form_submit_button("保存")
    if save:
        payload = {
            "name": name,
            "alias_names": alias_names,
            "origin_prefecture": origin_prefecture or None,
            "developer": developer,
            "registered_year": registered_year,
            "description": description,
            "skin_color": skin_color,
            "flesh_color": flesh_color,
            "brix_min": brix_min,
            "brix_max": brix_max,
            "acidity_level": acidity_level,
            "harvest_start_month": harvest_start_month,
            "harvest_end_month": harvest_end_month,
            "tags": tags,
        }
        parent_links = [{"parent_variety_id": pid, "parent_order": idx + 1} for idx, pid in enumerate(parent_ids)]
        try:
            if edit_id == "新規作成":
                new_id = create_variety(payload, parent_links)
                for file in uploaded_files[:5]:
                    upload_variety_image(new_id, file.name, file.getvalue())
                st.success("作成しました。")
            else:
                update_variety(edit_id, payload, parent_links)
                for file in uploaded_files[:5]:
                    upload_variety_image(edit_id, file.name, file.getvalue())
                st.success("更新しました。")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    if edit_id != "新規作成":
        images = list_images_with_signed_urls("variety_images", "variety_id", edit_id)
        primary_image_id = st.selectbox(
            "メイン画像",
            [""] + [img["id"] for img in images],
            format_func=lambda x: next((img["file_name"] for img in images if img["id"] == x), "未設定"),
            key="primary_image_select",
        )
        if primary_image_id and st.button("メイン画像を設定"):
            set_primary_variety_image(edit_id, primary_image_id)
            st.success("メイン画像を更新しました。")
            st.rerun()

with tab_deleted:
    page, page_size = render_pagination_controls("variety_deleted")
    deleted_rows, _ = list_varieties(include_deleted=True, page=page, page_size=page_size)
    deleted_rows = [row for row in deleted_rows if row.get("deleted_at")]
    render_table(deleted_rows)
    restore_id = st.selectbox("復元対象", [""] + [r["id"] for r in deleted_rows], format_func=lambda x: next((r["name"] for r in deleted_rows if r["id"] == x), ""))
    if restore_id and st.button("復元する"):
        try:
            restore_variety(restore_id)
            st.success("復元しました。")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
