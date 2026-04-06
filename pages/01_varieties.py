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
    from src.components.layout import (
        render_action_bar,
        render_empty_state,
        render_hero_banner,
        render_info_card,
        render_kpi_cards,
        render_status_badge,
        render_surface,
    )
except ImportError:
    def render_hero_banner(
        title: str,
        description: str,
        *,
        eyebrow: str | None = None,
        chips: list[str] | None = None,
    ) -> None:
        """Fallback hero renderer for partially refreshed runtimes."""
        render_page_header(title, description)
        if eyebrow:
            st.caption(eyebrow)
        if chips:
            st.caption(" / ".join(chips))


    def render_action_bar(
        actions: list[str] | None = None,
        *,
        title: str | None = None,
        description: str | None = None,
    ) -> None:
        """Fallback action bar renderer for partially refreshed runtimes."""
        if title:
            st.write(f"**{title}**")
        if description:
            st.caption(description)
        if actions:
            st.caption(" / ".join(actions))


    def render_info_card(text: str) -> None:
        """Fallback info card renderer for partially refreshed runtimes."""
        plain = text.replace("<strong>", "").replace("</strong>", "").replace("<br>", " ")
        st.info(plain)

    def render_empty_state(
        message: str,
        *,
        title: str = "表示できるデータがありません",
        hint: str | None = None,
    ) -> None:
        """Fallback empty-state renderer for partially refreshed runtimes."""
        if title:
            st.caption(title)
        st.info(" ".join(part for part in [message, hint] if part))


    def render_kpi_cards(items: list[tuple[str, str, str | None]]) -> None:
        """Fallback KPI card renderer for partially refreshed runtimes."""
        columns = st.columns(len(items))
        for column, (label, value, sub_text) in zip(columns, items, strict=True):
            column.metric(label, value, help=sub_text)


    def render_surface(
        content: str,
        *,
        title: str | None = None,
        subtitle: str | None = None,
        tone: str = "default",
        elevated: bool = False,
    ) -> None:
        """Fallback surface renderer for partially refreshed runtimes."""
        _ = tone, elevated
        if title:
            st.write(f"**{title}**")
        if subtitle:
            st.caption(subtitle)
        plain = content.replace("<strong>", "").replace("</strong>", "").replace("<br>", " ")
        st.write(plain)


    def render_status_badge(label: str, tone: str = "neutral", *, icon: str | None = None) -> str:
        """Fallback status badge renderer for partially refreshed runtimes."""
        _ = tone
        badge_text = f"{icon} {label}" if icon else label
        st.caption(badge_text)
        return badge_text

def _completion_badge_tone(completion_rate: float) -> str:
    if completion_rate >= 80:
        return "success"
    if completion_rate >= 40:
        return "info"
    return "warning"


def _build_variety_summary(row: dict, *, discovered: bool, max_length: int = 96) -> str:
    if not discovered:
        return "試食評価を1件登録すると、詳細情報と画像が開示されます。"
    summary = (row.get("characteristics_summary") or row.get("description") or "").strip()
    if not summary:
        return "特性情報は準備中です。"
    if len(summary) > max_length:
        return f"{summary[:max_length].rstrip()}…"
    return summary


def _render_discovered_dex_card(row: dict, review_count: int) -> bool:
    token = str(row.get("registration_number") or row.get("application_number") or "----")
    title = row.get("name") or "名称未設定"
    short_description = _build_variety_summary(row, discovered=True)
    render_surface(
        f"登録番号: No.{token}\n\n{short_description}\n\nレビュー件数: **{int(review_count)}件**",
        title=title,
        subtitle="発見済み",
        tone="accent",
        elevated=True,
    )
    return st.button("詳細を見る", key=f"dex_open_discovered_{row['id']}", use_container_width=True)


def _render_undiscovered_dex_row(row: dict) -> bool:
    token = str(row.get("registration_number") or row.get("application_number") or "----")
    with st.container(border=True):
        info_col, action_col = st.columns([4.2, 1.2])
        with info_col:
            st.markdown(f"**No.{token} ？？？？？**")
            st.caption(_build_variety_summary(row, discovered=False))
        with action_col:
            return st.button("開示条件を見る", key=f"dex_open_undiscovered_{row['id']}", use_container_width=True)
    return False


def _open_variety_detail(variety_id: str) -> None:
    st.session_state["selected_variety_id"] = variety_id
    st.rerun()


st.set_page_config(page_title="品種管理", layout="wide")
require_admin_session()
inject_app_style()
render_sidebar(active_page="varieties")
render_hero_banner(
    "品種管理",
    "登録情報の参照・編集・削除復元・画像管理を行います。",
    eyebrow="品種データベース",
    chips=["図鑑モード", "レビュー連動開示", "画像管理"],
)
render_action_bar(
    title="画面の使い方",
    description="一覧で探索、作成・編集で更新、削除済みから復元できます。",
    actions=["一覧", "作成・編集", "削除済み"],
)


tab_list, tab_edit, tab_deleted = st.tabs(["一覧", "作成・編集", "削除済み"])

with tab_list:
    render_section_title("品種一覧", "フィルタ / 一覧 / 詳細パネルで管理できます。")
    with st.container(border=True):
        f1, f2, f3 = st.columns([2, 1, 1.4], gap="medium")
        with f1:
            keyword = st.text_input("キーワード", key="variety_keyword")
        with f2:
            prefecture = st.selectbox("都道府県", [""] + PREFECTURES, key="variety_pref_filter")
        with f3:
            discovery_filter = st.radio("表示状態", ["すべて", "発見済み", "未発見"], horizontal=True, key="variety_discovery_filter")
        page, page_size = render_pagination_controls("variety_list")

    rows, total = list_varieties(
        keyword=keyword or None,
        prefecture=prefecture or None,
        page=page,
        page_size=page_size,
        fields="id,name,origin_prefecture,registration_number,application_number,description,characteristics_summary",
    )
    review_counts = get_review_counts_for_varieties([row["id"] for row in rows])
    progress = get_pokedex_progress()
    completion_ratio = (float(progress["completion_rate"]) / 100) if progress["total_varieties"] else 0.0

    render_kpi_cards(
        [
            ("図鑑登録数", str(progress["total_varieties"]), None),
            ("発見済み", str(progress["discovered_count"]), "レビュー1件以上"),
            ("未発見", str(progress["undiscovered_count"]), None),
            ("図鑑達成率", f"{progress['completion_rate']}%", None),
        ]
    )
    st.progress(completion_ratio)
    st.caption(
        f"進捗: 全{progress['total_varieties']}件中、発見 {progress['discovered_count']}件 / 未発見 {progress['undiscovered_count']}件"
    )

    if discovery_filter == "発見済み":
        visible_rows = [row for row in rows if review_counts.get(row["id"], 0) > 0]
    elif discovery_filter == "未発見":
        visible_rows = [row for row in rows if review_counts.get(row["id"], 0) == 0]
    else:
        visible_rows = rows

    if "variety_selected_from_list" not in st.session_state:
        st.session_state["variety_selected_from_list"] = ""
    preselected = st.session_state.pop("selected_variety_id", "")
    if preselected:
        st.session_state["variety_selected_from_list"] = preselected

    list_col, detail_col = st.columns([1.4, 1], gap="large")
    with list_col:
        render_section_title("一覧", f"現在ページ: {len(visible_rows)}件 / 全体: {total}件")
        if not visible_rows:
            render_empty_state(
                "条件に一致する品種がありません。",
                title="表示できる品種がありません",
                hint="キーワードや都道府県条件を調整してください。",
            )
        else:
            for row in visible_rows:
                variety_id = row["id"]
                discovered = review_counts.get(variety_id, 0) > 0
                display_name = row.get("name") or "名称未設定"
                if not discovered:
                    token = row.get("registration_number") or row.get("application_number") or "----"
                    display_name = f"No.{token} ？？？？？"
                with st.container(border=True):
                    st.markdown(f"**{display_name}**")
                    st.caption(f"都道府県: {row.get('origin_prefecture') or '-'}")
                    render_status_badge("発見済み" if discovered else "未発見", tone="success" if discovered else "neutral")
                    st.caption(f"レビュー件数: {review_counts.get(variety_id, 0)}件")
                    action_col, quick_col = st.columns(2, gap="small")
                    with action_col:
                        if st.button("詳細を表示", key=f"variety_open_{variety_id}", use_container_width=True):
                            st.session_state["variety_selected_from_list"] = variety_id
                            st.rerun()
                    with quick_col:
                        if not discovered:
                            st.page_link("pages/02_reviews.py", label="📝 レビュー登録", use_container_width=True)

    with detail_col:
        selected_id = st.session_state.get("variety_selected_from_list", "")
        if selected_id and not any(row["id"] == selected_id for row in visible_rows):
            selected_id = visible_rows[0]["id"] if visible_rows else ""
            st.session_state["variety_selected_from_list"] = selected_id

        if selected_id:
            discovered = review_counts.get(selected_id, 0) > 0
            detail = get_variety_detail(selected_id)
            if detail:
                if not discovered:
                    render_surface(
                        f"No.{str(detail.get('registration_number') or '----')} は未発見です。\n\n"
                        "「試食評価」ページでこの品種のレビューを1件登録すると、詳細情報と画像が開示されます。",
                        title="情報ロック中",
                        tone="soft",
                    )
                    st.page_link("pages/02_reviews.py", label="📝 試食評価を開く", use_container_width=True)
                else:
                    render_info_card(
                        f"**{detail.get('name', '-')}**\n\n"
                        f"登録番号: {detail.get('registration_number') or '-'} / "
                        f"出願番号: {detail.get('application_number') or '-'}"
                    )
                    st.write(
                        {
                            "都道府県": detail.get("origin_prefecture") or "-",
                            "開発者": detail.get("developer") or "-",
                            "糖度(下限)": detail.get("brix_min"),
                            "糖度(上限)": detail.get("brix_max"),
                            "酸味レベル": detail.get("acidity_level") or "-",
                            "収穫期": f"{detail.get('harvest_start_month') or '-'}〜{detail.get('harvest_end_month') or '-'}月",
                        }
                    )
                    if detail.get("characteristics_summary"):
                        render_surface(detail["characteristics_summary"], title="特性の概要", tone="accent")
                    elif detail.get("description"):
                        render_surface(detail["description"], title="説明", tone="soft")
                    images = list_images_with_signed_urls("variety_images", "variety_id", selected_id)
                    render_image_gallery(images, "variety")
                    if st.button("この品種を削除", key=f"delete_variety_{selected_id}", use_container_width=True):
                        soft_delete_variety(selected_id)
                        st.success("削除しました。")
                        st.rerun()
            else:
                render_empty_state("品種詳細を取得できませんでした。", title="品種詳細を表示できません")
        else:
            render_empty_state("一覧から品種を選択すると詳細が表示されます。", title="品種未選択")

with tab_edit:
    render_section_title("作成・編集", "品種情報と画像を登録・更新します。")
    render_action_bar(
        title="入力ガイド",
        description="基本情報・味覚指標・親品種リンクを入力後、必要に応じて画像をアップロードしてください。",
        actions=["基本情報", "味覚指標", "親品種", "画像アップロード"],
    )

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
        render_surface(
            "画像は最大5枚まで登録できます。メイン画像を設定すると一覧や関連画面での表示基準になります。",
            tone="soft",
        )
        images = list_images_with_signed_urls("variety_images", "variety_id", edit_id)
        render_image_gallery(images, "variety_edit")
        primary_image_id = st.selectbox(
            "メイン画像",
            [""] + [img["id"] for img in images],
            format_func=lambda x: next((img["file_name"] for img in images if img["id"] == x), "未設定"),
            key="primary_image_select",
        )
        if primary_image_id and st.button("メイン画像を設定", use_container_width=True):
            set_primary_variety_image(edit_id, primary_image_id)
            st.success("メイン画像を更新しました。")
            st.rerun()

with tab_deleted:
    render_section_title("削除済み品種", "復元対象を選択して戻せます。")
    render_surface("誤削除した品種はここから復元できます。復元後は一覧タブですぐ確認できます。", tone="soft")
    page, page_size = render_pagination_controls("variety_deleted")
    deleted_rows, _ = list_varieties(include_deleted=True, page=page, page_size=page_size)
    deleted_rows = [row for row in deleted_rows if row.get("deleted_at")]
    if deleted_rows:
        render_table(deleted_rows)
    else:
        render_empty_state(
            "削除済み品種はありません。",
            title="復元対象はありません",
            hint="削除操作を行った品種のみ、このタブに表示されます。",
        )
    restore_id = st.selectbox(
        "復元対象",
        [""] + [r["id"] for r in deleted_rows],
        format_func=lambda x: next((r["name"] for r in deleted_rows if r["id"] == x), "未選択"),
    )
    if st.button("選択した品種を復元", use_container_width=True, disabled=not restore_id):
        try:
            restore_variety(restore_id)
            st.success("復元しました。")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
