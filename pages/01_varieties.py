"""Varieties management page."""

from __future__ import annotations

import streamlit as st

from src.components.forms import comma_values_input
from src.components.image_gallery import render_image_gallery
from src.components.layout import inject_app_style, render_page_header, render_section_title
from src.components.pagination import render_pagination_controls
from src.components.sidebar import render_sidebar
from src.components.tables import render_table
from src.constants.enums import AcidityLevel
from src.constants.prefectures import PREFECTURES
from src.services.auth_service import require_admin_session
from src.services.storage_service import (
    list_images_with_signed_urls,
    set_primary_variety_image,
    upload_variety_image,
)
from src.services.variety_service import (
    create_variety,
    get_pokedex_progress,
    get_review_counts_for_varieties,
    get_variety_detail,
    list_active_varieties,
    list_varieties,
    restore_variety,
    soft_delete_variety,
    update_variety,
)

try:
    from src.components.layout import render_info_card, render_kpi_cards
except ImportError:
    def render_info_card(text: str) -> None:
        """Fallback info card renderer for partially refreshed runtimes."""
        plain = text.replace("<strong>", "").replace("</strong>", "").replace("<br>", " ")
        st.info(plain)


    def render_kpi_cards(items: list[tuple[str, str, str | None]]) -> None:
        """Fallback KPI card renderer for partially refreshed runtimes."""
        columns = st.columns(len(items))
        for column, (label, value, sub_text) in zip(columns, items, strict=True):
            column.metric(label, value, help=sub_text)


def _render_dex_card(row: dict, discovered: bool, review_count: int) -> None:
    token = row.get("registration_number") or row.get("application_number") or "----"
    title = row.get("name") if discovered else "？？？？？"
    status_label = "発見済み" if discovered else "未発見"
    status_color = "#198754" if discovered else "#8b8f96"
    short_description = (row.get("description") or row.get("characteristics_summary") or "").strip()
    if not discovered:
        short_description = "レビュー登録で詳細が開示されます。"
    if len(short_description) > 70:
        short_description = f"{short_description[:70]}..."
    st.markdown(
        f"""
        <div style="
            border:1px solid {'#d5efe0' if discovered else '#e4e6ea'};
            border-radius:14px;
            padding:12px 12px 10px 12px;
            background:{'#fff' if discovered else '#f8f9fb'};
            min-height:160px;
            box-shadow:0 4px 14px rgba(95,41,63,0.05);
        ">
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <span style="font-size:0.78rem;color:#6c757d;">No.{token}</span>
            <span style="font-size:0.72rem;color:#fff;background:{status_color};padding:2px 8px;border-radius:999px;">{status_label}</span>
          </div>
          <div style="margin-top:8px;font-weight:700;color:#7a1236;font-size:1.02rem;">{title}</div>
          <div style="margin-top:6px;font-size:0.82rem;color:#5f646d;">{short_description}</div>
          <div style="margin-top:10px;font-size:0.76rem;color:#6f5a62;">レビュー件数: {review_count}件</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


st.set_page_config(page_title="品種管理", layout="wide")
require_admin_session()
inject_app_style()
render_sidebar()
render_page_header("品種管理", "登録情報の参照・編集・削除復元・画像管理を行います。")

tab_list, tab_edit, tab_deleted = st.tabs(["一覧", "作成・編集", "削除済み"])

with tab_list:
    render_section_title("品種図鑑", "レビューを登録しながら図鑑を埋めていく体験で品種管理できます。")
    f1, f2, f3 = st.columns(3)
    with f1:
        keyword = st.text_input("キーワード", key="variety_keyword")
    with f2:
        prefecture = st.selectbox("都道府県", [""] + PREFECTURES, key="variety_pref_filter")
    with f3:
        discovered_only = st.checkbox("発見済みのみ表示", value=False)
    page, page_size = render_pagination_controls("variety_list")
    rows, total = list_varieties(
        keyword=keyword or None,
        prefecture=prefecture or None,
        page=page,
        page_size=page_size,
        fields="id,name,registration_number,application_number,description,characteristics_summary",
    )
    review_counts = get_review_counts_for_varieties([row["id"] for row in rows])
    row_by_id = {row["id"]: row for row in rows}
    progress = get_pokedex_progress()
    render_kpi_cards(
        [
            ("図鑑登録数", str(progress["total_varieties"]), None),
            ("発見済み", str(progress["discovered_count"]), "レビュー1件以上"),
            ("未発見", str(progress["undiscovered_count"]), None),
            ("図鑑達成率", f"{progress['completion_rate']}%", None),
        ]
    )

    card_rows = rows
    if discovered_only:
        card_rows = [row for row in rows if review_counts.get(row["id"], 0) > 0]

    st.caption(f"現在ページ表示件数: {len(card_rows)}件 / 全体: {total}件")
    if card_rows:
        columns = st.columns(3)
        for index, row in enumerate(card_rows):
            review_count = review_counts.get(row["id"], 0)
            discovered = review_count > 0
            with columns[index % 3]:
                _render_dex_card(row, discovered=discovered, review_count=review_count)
                if st.button("詳細を見る", key=f"dex_open_{row['id']}", use_container_width=True):
                    st.session_state["selected_variety_id"] = row["id"]
                    st.rerun()
    else:
        st.info("条件に一致する図鑑カードがありません。フィルタを緩めて再表示してください。")

    preselected = st.session_state.pop("selected_variety_id", "")
    options = [""] + [r["id"] for r in rows]
    selected_id = st.selectbox(
        "詳細表示する品種（図鑑カードからも選択可能）",
        options,
        index=options.index(preselected) if preselected in options else 0,
        format_func=lambda x: (
            "未選択"
            if not x
            else (
                row_by_id[x]["name"]
                if review_counts.get(x, 0) > 0
                else f"No.{row_by_id[x].get('registration_number') or '----'} ？？？？？"
            )
            if x in row_by_id
            else "未選択"
        ),
    )
    if selected_id:
        discovered = review_counts.get(selected_id, 0) > 0
        detail = get_variety_detail(selected_id)
        c1, c2 = st.columns([3, 2])
        with c1:
            if detail:
                if not discovered:
                    render_info_card(
                        f"<strong>No.{detail.get('registration_number') or '----'}</strong><br>"
                        "この品種は未発見です。レビューを登録すると詳細データが開示されます。"
                    )
                    st.info("「試食評価」ページでこの品種のレビューを1件登録すると図鑑が更新されます。")
                else:
                    render_info_card(
                        f"<strong>{detail.get('name', '-')}</strong><br>"
                        f"登録番号: {detail.get('registration_number') or '-'} / "
                        f"出願番号: {detail.get('application_number') or '-'}"
                    )
                    d1, d2 = st.columns(2)
                    with d1:
                        st.write("**基本情報**")
                        st.write(
                            {
                                "学名": detail.get("scientific_name") or "-",
                                "和名": detail.get("japanese_name") or "-",
                                "登録年月日": detail.get("registration_date") or "-",
                                "出願年月日": detail.get("application_date") or "-",
                                "出願公表年月日": detail.get("publication_date") or "-",
                                "開発者": detail.get("developer") or "-",
                                "育成者権者": detail.get("breeder_right_holder") or "-",
                                "出願者": detail.get("applicant") or "-",
                                "育成地": detail.get("breeding_place") or "-",
                                "都道府県": detail.get("origin_prefecture") or "-",
                            }
                        )
                    with d2:
                        st.write("**品質・運用情報**")
                        st.write(
                            {
                                "糖度(下限)": detail.get("brix_min"),
                                "糖度(上限)": detail.get("brix_max"),
                                "酸味レベル": detail.get("acidity_level") or "-",
                                "収穫開始月": detail.get("harvest_start_month"),
                                "収穫終了月": detail.get("harvest_end_month"),
                                "利用条件": detail.get("usage_conditions") or "-",
                                "権利存続期間": detail.get("right_duration") or "-",
                                "備考": detail.get("remarks") or "-",
                            }
                        )
                    if detail.get("characteristics_summary"):
                        st.write("**特性の概要**")
                        st.write(detail["characteristics_summary"])
                    elif detail.get("description"):
                        st.write("**説明**")
                        st.write(detail["description"])
            else:
                st.info("品種詳細を取得できませんでした。")
        with c2:
            if discovered:
                images = list_images_with_signed_urls("variety_images", "variety_id", selected_id)
                render_image_gallery(images, "variety")
            else:
                st.info("未発見のため画像表示はロックされています。")
        if discovered and st.button("この品種を削除", key=f"delete_variety_{selected_id}"):
            soft_delete_variety(selected_id)
            st.success("削除しました。")
            st.rerun()

with tab_edit:
    render_section_title("作成・編集", "品種情報と画像を登録・更新します。")
    active = list_active_varieties()
    edit_id = st.selectbox(
        "編集対象",
        ["新規作成"] + [v["id"] for v in active],
        format_func=lambda x: "新規作成" if x == "新規作成" else next((v["name"] for v in active if v["id"] == x), x),
    )
    base = get_variety_detail(edit_id) if edit_id != "新規作成" else {}
    with st.form("variety_form"):
        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input("品種名*", value=base.get("name", ""))
            alias_names = comma_values_input("別名 (カンマ区切り)", "alias_names_input", 20, 50)
            origin_prefecture = st.selectbox(
                "都道府県",
                [""] + PREFECTURES,
                index=([""] + PREFECTURES).index(base.get("origin_prefecture", "")),
            )
            developer = st.text_input("開発者", value=base.get("developer", ""))
            registered_year = st.number_input(
                "登録年",
                min_value=1900,
                max_value=2100,
                value=int(base.get("registered_year") or 2024),
            )
            skin_color = st.text_input("果皮色", value=base.get("skin_color", ""))
            flesh_color = st.text_input("果肉色", value=base.get("flesh_color", ""))
        with c2:
            brix_min = st.number_input("糖度下限", min_value=0.0, max_value=30.0, value=float(base.get("brix_min") or 0.0))
            brix_max = st.number_input("糖度上限", min_value=0.0, max_value=30.0, value=float(base.get("brix_max") or 0.0))
            acidity_level = st.selectbox(
                "酸味",
                [x.value for x in AcidityLevel],
                index=[x.value for x in AcidityLevel].index(base.get("acidity_level", "unknown")),
            )
            harvest_start_month = st.number_input(
                "収穫開始月",
                min_value=1,
                max_value=12,
                value=int(base.get("harvest_start_month") or 1),
            )
            harvest_end_month = st.number_input(
                "収穫終了月",
                min_value=1,
                max_value=12,
                value=int(base.get("harvest_end_month") or 12),
            )
            tags = comma_values_input("タグ (カンマ区切り)", "variety_tags_input", 20, 30)
            parent_ids = st.multiselect(
                "親品種",
                options=[v["id"] for v in active if v["id"] != edit_id],
                format_func=lambda i: next((v["name"] for v in active if v["id"] == i), i),
            )
        description = st.text_area("説明", value=base.get("description", ""), height=140)
        uploaded_files = st.file_uploader(
            "画像アップロード (最大5枚)",
            type=["jpg", "jpeg", "png", "webp"],
            accept_multiple_files=True,
        )
        save = st.form_submit_button("保存", use_container_width=True)

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
                target_id = create_variety(payload, parent_links)
                success_message = "作成しました。"
            else:
                update_variety(edit_id, payload, parent_links)
                target_id = edit_id
                success_message = "更新しました。"
            for file in uploaded_files[:5]:
                upload_variety_image(target_id, file.name, file.getvalue())
            st.success(success_message)
            st.rerun()
        except Exception as exc:
            st.error(str(exc))

    if edit_id != "新規作成":
        render_section_title("画像管理")
        images = list_images_with_signed_urls("variety_images", "variety_id", edit_id)
        render_image_gallery(images, "variety_edit")
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
    render_section_title("削除済み品種", "復元対象を選択して戻せます。")
    page, page_size = render_pagination_controls("variety_deleted")
    deleted_rows, _ = list_varieties(include_deleted=True, page=page, page_size=page_size)
    deleted_rows = [row for row in deleted_rows if row.get("deleted_at")]
    render_table(deleted_rows)
    restore_id = st.selectbox(
        "復元対象",
        [""] + [r["id"] for r in deleted_rows],
        format_func=lambda x: next((r["name"] for r in deleted_rows if r["id"] == x), "未選択"),
    )
    if restore_id and st.button("復元する"):
        try:
            restore_variety(restore_id)
            st.success("復元しました。")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
