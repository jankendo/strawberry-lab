"""Varieties management page."""

from __future__ import annotations

from html import escape

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


def _to_html_text(text: str) -> str:
    return escape(text).replace("\n", "<br>")


def _completion_badge_tone(completion_rate: float) -> str:
    if completion_rate >= 80:
        return "success"
    if completion_rate >= 40:
        return "info"
    return "warning"


def _render_dex_card(row: dict, discovered: bool, review_count: int) -> None:
    token = escape(str(row.get("registration_number") or row.get("application_number") or "----"))
    title = escape(row.get("name") or "？？？？？") if discovered else "？？？？？"
    status_label = "発見済み" if discovered else "未発見"
    status_class = "success" if discovered else "neutral"

    short_description = (row.get("description") or row.get("characteristics_summary") or "").strip()
    if not discovered:
        short_description = "レビュー登録で詳細が開示されます。"
    if len(short_description) > 70:
        short_description = f"{short_description[:70]}..."
    short_description_html = _to_html_text(short_description)

    render_surface(
        (
            '<div style="display:flex;justify-content:space-between;align-items:center;gap:0.4rem;">'
            f'<span class="sl-muted" style="font-size:0.75rem;">No.{token}</span>'
            f'<span class="sl-badge sl-badge-{status_class}">{status_label}</span>'
            "</div>"
            f'<div style="margin-top:0.42rem;font-weight:700;color:#7a1236;font-size:1.02rem;">{title}</div>'
            f'<div style="margin-top:0.34rem;font-size:0.82rem;color:#5f646d;line-height:1.52;">{short_description_html}</div>'
            f'<div style="margin-top:0.52rem;font-size:0.76rem;color:#6f5a62;">レビュー件数: {int(review_count)}件</div>'
        ),
        tone="accent" if discovered else "soft",
        elevated=True,
    )


st.set_page_config(page_title="品種管理", layout="wide")
require_admin_session()
inject_app_style()
render_sidebar()
render_hero_banner(
    "品種管理",
    "登録情報の参照・編集・削除復元・画像管理を行います。",
    eyebrow="Strawberry Variety Database",
    chips=["図鑑モード", "レビュー連動開示", "画像管理"],
)
render_action_bar(
    title="画面の使い方",
    description="一覧で探索、作成・編集で更新、削除済みから復元できます。",
    actions=["一覧", "作成・編集", "削除済み"],
)


tab_list, tab_edit, tab_deleted = st.tabs(["一覧", "作成・編集", "削除済み"])

with tab_list:
    render_section_title("品種図鑑", "レビューを登録しながら図鑑を埋めていく体験で品種管理できます。")
    render_surface(
        "レビューを1件登録すると、未発見カードの詳細情報と画像が順次開示されます。",
        title="図鑑ルール",
        subtitle="Pokédex Discovery",
        tone="soft",
    )
    render_action_bar(
        title="検索フィルタ",
        description="キーワード・都道府県・発見状態で表示を絞り込めます。",
        actions=["キーワード", "都道府県", "発見済みのみ表示"],
    )

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

    badge_col_1, badge_col_2, badge_col_3 = st.columns(3)
    with badge_col_1:
        render_status_badge(f"発見済み {progress['discovered_count']}種", tone="success", icon="✅")
    with badge_col_2:
        render_status_badge(f"未発見 {progress['undiscovered_count']}種", tone="neutral", icon="🔒")
    with badge_col_3:
        render_status_badge(
            f"達成率 {progress['completion_rate']}%",
            tone=_completion_badge_tone(float(progress["completion_rate"])),
            icon="📘",
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
        render_surface("条件に一致する図鑑カードがありません。フィルタを緩めて再表示してください。", tone="soft")

    preselected = st.session_state.pop("selected_variety_id", "")
    options = [""] + [r["id"] for r in rows]
    render_section_title("品種詳細", "図鑑カードまたはプルダウンから選択できます。")
    selected_id = st.selectbox(
        "詳細表示する品種",
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
                    render_surface(
                        f"No.{escape(str(detail.get('registration_number') or '----'))} は未発見です。<br>"
                        "「試食評価」ページでこの品種のレビューを1件登録すると詳細データが開示されます。",
                        title="情報ロック中",
                        subtitle="図鑑発見条件",
                        tone="soft",
                        elevated=True,
                    )
                else:
                    render_info_card(
                        f"<strong>{detail.get('name', '-')}</strong><br>"
                        f"登録番号: {detail.get('registration_number') or '-'} / "
                        f"出願番号: {detail.get('application_number') or '-'}"
                    )
                    d1, d2 = st.columns(2)
                    with d1:
                        render_surface("登録情報と開発背景を確認できます。", title="基本情報", tone="soft")
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
                        render_surface("品質・運用条件を確認できます。", title="品質・運用情報", tone="soft")
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
                        render_surface(_to_html_text(detail["characteristics_summary"]), title="特性の概要", tone="accent")
                    elif detail.get("description"):
                        render_surface(_to_html_text(detail["description"]), title="説明", tone="soft")
            else:
                st.info("品種詳細を取得できませんでした。")
        with c2:
            if discovered:
                render_surface(
                    "登録済み画像を確認できます。必要に応じて作成・編集タブでメイン画像を更新してください。",
                    title="画像プレビュー",
                    tone="soft",
                )
                images = list_images_with_signed_urls("variety_images", "variety_id", selected_id)
                render_image_gallery(images, "variety")
            else:
                render_surface("未発見のため画像表示はロックされています。", title="画像ロック中", tone="soft")
        if discovered and st.button("この品種を削除", key=f"delete_variety_{selected_id}"):
            soft_delete_variety(selected_id)
            st.success("削除しました。")
            st.rerun()

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
        if primary_image_id and st.button("メイン画像を設定"):
            set_primary_variety_image(edit_id, primary_image_id)
            st.success("メイン画像を更新しました。")
            st.rerun()

with tab_deleted:
    render_section_title("削除済み品種", "復元対象を選択して戻せます。")
    render_surface("誤削除した品種はここから復元できます。復元後は一覧タブですぐ確認できます。", tone="soft")
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
