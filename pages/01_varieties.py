"""Varieties management page."""

from __future__ import annotations

import streamlit as st

from src.components.forms import comma_values_input
from src.components.image_gallery import render_image_gallery
from src.components.layout import inject_app_style, render_page_header, render_section_title
from src.components.pagination import render_pagination_controls
from src.components.sidebar import render_primary_nav, render_sidebar
from src.components.swipe_actions import (
    render_swipe_action_layer,
    render_swipe_action_row_marker,
    render_swipe_action_secondary_marker,
)
from src.components.tables import is_mobile_client, render_table
from src.components.transitions import (
    render_view_transition_layer,
    render_view_transition_shared_element,
    render_view_transition_trigger,
)
from src.constants.enums import AcidityLevel
from src.constants.prefectures import PREFECTURES
from src.services.auth_service import require_admin_session
from src.services.storage_service import (
    list_primary_variety_images_with_signed_urls,
    list_images_with_signed_urls,
    set_primary_variety_image,
    upload_variety_image,
)
from src.services.variety_service import (
    create_variety,
    get_latest_review_summary_for_varieties,
    get_pokedex_progress,
    get_review_counts_for_varieties,
    get_variety_detail,
    list_active_varieties,
    list_varieties,
    list_varieties_for_list_tab,
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


_VARIETY_SECTION_ORDER = ["一覧", "作成・編集", "削除済み"]
_DISCOVERY_FILTER_OPTIONS = ["すべて", "発見済み", "未発見"]
_DISCOVERY_FILTER_DEFAULT = "発見済み"
_ACIDITY_LABELS = {"low": "低め", "medium": "ほどよい", "high": "しっかり"}
_LATEST_REVIEW_METRICS: list[tuple[str, str, int]] = [
    ("総合", "overall", 10),
    ("甘味", "sweetness", 5),
    ("酸味", "sourness", 5),
    ("香り", "aroma", 5),
    ("食感", "texture", 5),
    ("見た目", "appearance", 5),
]
_VARIETY_MOBILE_SWIPE_SCOPE = "varieties-mobile-card-actions"


def _resolve_select_index(options: list[str], value: object, *, fallback: int = 0) -> int:
    text = str(value or "").strip()
    if text in options:
        return options.index(text)
    if 0 <= fallback < len(options):
        return fallback
    return 0


def _build_variety_summary(row: dict, *, discovered: bool, max_length: int = 96) -> str:
    if not discovered:
        return "試食評価を1件登録すると、詳細情報と画像が開示されます。"
    summary = (row.get("characteristics_summary") or row.get("description") or "").strip()
    if not summary:
        return "特性情報は準備中です。"
    if len(summary) > max_length:
        return f"{summary[:max_length].rstrip()}…"
    return summary


def _clean_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.lower() in {"unknown", "null", "none", "-", "--"}:
        return None
    return text


def _format_numeric(value: object) -> str | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return f"{number:.1f}".rstrip("0").rstrip(".")


def _format_score(value: object, *, scale: int) -> str | None:
    try:
        score = int(value)
    except (TypeError, ValueError):
        return None
    if score <= 0:
        return None
    return f"{score}/{scale}"


def _format_month(value: object) -> int | None:
    try:
        month = int(value)
    except (TypeError, ValueError):
        return None
    return month if 1 <= month <= 12 else None


def _format_harvest_window(start_month: object, end_month: object) -> str | None:
    start = _format_month(start_month)
    end = _format_month(end_month)
    if start and end:
        return f"{start}〜{end}月"
    if start:
        return f"{start}月〜"
    if end:
        return f"〜{end}月"
    return None


def _format_brix_range(detail: dict) -> str | None:
    brix_min = _format_numeric(detail.get("brix_min"))
    brix_max = _format_numeric(detail.get("brix_max"))
    if brix_min and brix_max:
        return f"{brix_min}〜{brix_max}"
    if brix_min:
        return f"{brix_min}以上"
    if brix_max:
        return f"{brix_max}以下"
    return None


def _format_acidity_label(value: object) -> str | None:
    text = _clean_text(value)
    if not text:
        return None
    return _ACIDITY_LABELS.get(text.lower(), text)


def _pick_primary_image(images: list[dict]) -> dict | None:
    if not images:
        return None
    for image in images:
        if image.get("is_primary"):
            return image
    return images[0]


def _render_variety_thumbnail(image: dict | None, *, discovered: bool, show_caption: bool = True) -> None:
    signed_url = _clean_text((image or {}).get("signed_url")) if image else None
    if discovered and signed_url:
        st.image(signed_url, caption=_clean_text(image.get("file_name")) if show_caption else None, use_container_width=True)
        return
    st.markdown("#### 🔒" if not discovered else "#### 🖼️")
    if show_caption:
        st.caption("発見後に画像が開示されます。" if not discovered else "画像未登録")


def _latest_review_line(review_summary: dict | None) -> str | None:
    if not review_summary:
        return None
    overall = _format_score(review_summary.get("overall"), scale=10)
    tasted_date = _clean_text(review_summary.get("tasted_date"))
    if overall and tasted_date:
        return f"最新評価: {overall}（{tasted_date}）"
    if overall:
        return f"最新評価: {overall}"
    return None


def _render_detail_attribute_grid(title: str, items: list[tuple[str, str]], *, mobile_client: bool) -> None:
    if not items:
        return
    render_section_title(title)
    per_row = 1 if mobile_client else 2
    for start in range(0, len(items), per_row):
        chunk = items[start : start + per_row]
        columns = st.columns(len(chunk), gap="small")
        for column, (label, value) in zip(columns, chunk, strict=True):
            with column:
                with st.container(border=True):
                    st.caption(label)
                    st.markdown(f"**{value}**")


def _render_variety_filters(*, mobile_client: bool) -> tuple[str, str, str]:
    if st.session_state.get("variety_discovery_filter") not in _DISCOVERY_FILTER_OPTIONS:
        st.session_state["variety_discovery_filter"] = _DISCOVERY_FILTER_DEFAULT
    with st.container(border=True):
        render_section_title("フィルタ", "条件を指定して表示対象を絞り込みます。")
        if mobile_client:
            keyword = st.text_input("キーワード", key="variety_keyword")
            prefecture = st.selectbox("都道府県", [""] + PREFECTURES, key="variety_pref_filter")
            discovery_filter = st.radio(
                "開示モード",
                _DISCOVERY_FILTER_OPTIONS,
                key="variety_discovery_filter",
            )
        else:
            f1, f2, f3 = st.columns([2, 1, 1.4], gap="medium")
            with f1:
                keyword = st.text_input("キーワード", key="variety_keyword")
            with f2:
                prefecture = st.selectbox("都道府県", [""] + PREFECTURES, key="variety_pref_filter")
            with f3:
                discovery_filter = st.radio(
                    "開示モード",
                    _DISCOVERY_FILTER_OPTIONS,
                    horizontal=True,
                    key="variety_discovery_filter",
                )
    return keyword, prefecture, discovery_filter


def _display_variety_name(row: dict, *, discovered: bool) -> str:
    if discovered:
        return _clean_text(row.get("name")) or "名称未設定"
    token = row.get("registration_number") or row.get("application_number") or "----"
    return f"No.{token} ？？？？？"


def _open_review_entry(variety_id: str) -> None:
    st.session_state["review_variety_id"] = variety_id
    st.switch_page("pages/02_reviews.py")


def _render_variety_list_item(
    row: dict,
    review_count: int,
    *,
    key_prefix: str,
    primary_image: dict | None = None,
    latest_review: dict | None = None,
) -> bool:
    discovered = review_count > 0
    with st.container(border=True):
        if discovered:
            image_col, info_col = st.columns([1, 2], gap="medium")
        else:
            image_col, info_col = None, st.container()
        if image_col is not None:
            with image_col:
                _render_variety_thumbnail(primary_image, discovered=True, show_caption=False)
        with info_col:
            st.markdown(f"**{_display_variety_name(row, discovered=discovered)}**")
            render_status_badge("発見済み" if discovered else "未発見", tone="success" if discovered else "neutral")
            if discovered:
                prefecture_text = _clean_text(row.get("origin_prefecture")) or "未登録"
                st.caption(f"都道府県: {prefecture_text}")
                st.caption(f"レビュー件数: {int(review_count)}件")
                latest_line = _latest_review_line(latest_review)
                if latest_line:
                    st.caption(latest_line)
                st.caption(_build_variety_summary(row, discovered=True, max_length=120))
            else:
                st.caption("レビュー未登録のため詳細は非表示です。")
                st.caption("試食評価を1件登録すると情報が開示されます。")
        return st.button("この品種を開く", key=f"{key_prefix}_{row['id']}", use_container_width=True)


def _render_mobile_variety_cards(
    rows: list[dict],
    review_counts: dict[str, int],
    primary_images: dict[str, dict],
    latest_reviews: dict[str, dict],
) -> str | None:
    render_swipe_action_layer(_VARIETY_MOBILE_SWIPE_SCOPE, threshold_px=72)
    selected_id: str | None = None
    for row in rows:
        variety_id = str(row["id"])
        review_count = int(review_counts.get(variety_id, 0))
        discovered = review_count > 0
        with st.container(border=True):
            if discovered:
                image_col, info_col = st.columns([1, 1.6], gap="small")
            else:
                image_col, info_col = None, st.container()
            if image_col is not None:
                with image_col:
                    render_view_transition_shared_element("varieties-mobile-list-detail", variety_id, role="source")
                    _render_variety_thumbnail(primary_images.get(variety_id), discovered=True, show_caption=False)
            with info_col:
                st.markdown(f"**{_display_variety_name(row, discovered=discovered)}**")
                render_status_badge("発見済み" if discovered else "未発見", tone="success" if discovered else "neutral")
                if discovered:
                    prefecture_text = _clean_text(row.get("origin_prefecture"))
                    if prefecture_text:
                        st.caption(f"都道府県: {prefecture_text}")
                    st.caption(f"レビュー件数: {review_count}件")
                    latest_line = _latest_review_line(latest_reviews.get(variety_id))
                    if latest_line:
                        st.caption(latest_line)
                    st.caption(_build_variety_summary(row, discovered=True, max_length=88))
                else:
                    st.caption("レビュー未登録（詳細ロック中）")
            render_swipe_action_row_marker(
                _VARIETY_MOBILE_SWIPE_SCOPE,
                variety_id,
                hint="左にスワイプで評価アクションを表示",
                reveal_label="操作を表示",
                hide_label="操作を閉じる",
            )
            render_view_transition_trigger(
                "varieties-mobile-list-detail",
                "list-to-detail",
                shared_key=variety_id,
                shared_role="source",
            )
            if st.button("詳細", key=f"variety_mobile_open_{variety_id}", use_container_width=True):
                selected_id = variety_id
            render_swipe_action_secondary_marker(_VARIETY_MOBILE_SWIPE_SCOPE, variety_id)
            quick_action_col = st.columns(1)[0]
            with quick_action_col:
                if st.button("評価", key=f"variety_mobile_review_{variety_id}", use_container_width=True, type="secondary"):
                    _open_review_entry(variety_id)
    return selected_id


def _render_variety_detail_panel(
    selected_id: str,
    *,
    discovered: bool,
    review_count: int,
    latest_review: dict | None,
    primary_image: dict | None,
    mobile_client: bool,
) -> None:
    detail = get_variety_detail(selected_id)
    if not detail:
        render_empty_state("品種詳細を取得できませんでした。", title="品種詳細を表示できません")
        return

    if not discovered:
        render_surface(
            f"No.{str(detail.get('registration_number') or '----')} は未発見です。\n\n"
            "「試食評価」ページでこの品種のレビューを1件登録すると、詳細情報と画像が開示されます。",
            title="情報ロック中",
            tone="soft",
        )
        if st.button("📝 この品種を評価", key=f"go_review_locked_{selected_id}", use_container_width=True, type="primary"):
            _open_review_entry(selected_id)
        return

    images = list_images_with_signed_urls("variety_images", "variety_id", selected_id)
    hero_image = _pick_primary_image(images) or primary_image
    name_text = _clean_text(detail.get("name")) or "名称未設定"
    registration_number = _clean_text(detail.get("registration_number"))
    application_number = _clean_text(detail.get("application_number"))
    hero_lines: list[str] = []
    if registration_number:
        hero_lines.append(f"登録番号: **{registration_number}**")
    if application_number:
        hero_lines.append(f"出願番号: **{application_number}**")
    hero_content = "\n\n".join(hero_lines) if hero_lines else "公開可能な基本情報を表示しています。"

    if mobile_client:
        render_view_transition_shared_element("varieties-mobile-list-detail", selected_id, role="target")
        _render_variety_thumbnail(hero_image, discovered=True)
        render_surface(
            hero_content,
            title=name_text,
            subtitle=f"レビュー件数: {review_count}件",
            tone="soft",
        )
        if st.button("📝 この品種を評価", key=f"go_review_mobile_{selected_id}", use_container_width=True, type="primary"):
            _open_review_entry(selected_id)
    else:
        hero_image_col, hero_meta_col = st.columns([1, 1.1], gap="medium")
        with hero_image_col:
            _render_variety_thumbnail(hero_image, discovered=True)
        with hero_meta_col:
            render_surface(
                hero_content,
                title=name_text,
                subtitle=f"レビュー件数: {review_count}件",
                tone="soft",
            )
            if st.button("📝 この品種を評価", key=f"go_review_desktop_{selected_id}", use_container_width=True, type="primary"):
                _open_review_entry(selected_id)

    if latest_review:
        latest_date = _clean_text(latest_review.get("tasted_date"))
        render_surface(
            "最新のレビュー評価を表示しています。",
            title="評価結果",
            subtitle=f"最新試食日: {latest_date}" if latest_date else None,
            tone="accent",
        )
        review_metrics: list[tuple[str, str, str | None]] = []
        for label, key, scale in _LATEST_REVIEW_METRICS:
            score_text = _format_score(latest_review.get(key), scale=scale)
            if score_text:
                review_metrics.append((label, score_text, None))
        if review_metrics:
            render_kpi_cards(review_metrics)

    profile_items: list[tuple[str, str]] = []
    origin_prefecture = _clean_text(detail.get("origin_prefecture"))
    developer = _clean_text(detail.get("developer"))
    registered_year = detail.get("registered_year")
    if origin_prefecture:
        profile_items.append(("都道府県", origin_prefecture))
    if developer:
        profile_items.append(("開発者", developer))
    if registered_year not in {None, ""}:
        profile_items.append(("登録年", str(registered_year)))

    trait_items: list[tuple[str, str]] = []
    brix_range = _format_brix_range(detail)
    if brix_range:
        trait_items.append(("糖度", brix_range))
    acidity_label = _format_acidity_label(detail.get("acidity_level"))
    if acidity_label:
        trait_items.append(("酸味レベル", acidity_label))
    harvest_window = _format_harvest_window(detail.get("harvest_start_month"), detail.get("harvest_end_month"))
    if harvest_window:
        trait_items.append(("収穫期", harvest_window))
    skin_color = _clean_text(detail.get("skin_color"))
    flesh_color = _clean_text(detail.get("flesh_color"))
    if skin_color:
        trait_items.append(("果皮色", skin_color))
    if flesh_color:
        trait_items.append(("果肉色", flesh_color))

    _render_detail_attribute_grid("基本情報", profile_items, mobile_client=mobile_client)
    _render_detail_attribute_grid("味・栽培の目安", trait_items, mobile_client=mobile_client)

    characteristics_summary = _clean_text(detail.get("characteristics_summary"))
    description = _clean_text(detail.get("description"))
    if characteristics_summary:
        render_surface(characteristics_summary, title="特性の概要", tone="accent")
    if description and description != characteristics_summary:
        render_surface(description, title="補足説明", tone="soft")

    if images:
        ordered_images = sorted(
            images,
            key=lambda image: (0 if image.get("is_primary") else 1, str(image.get("created_at") or "")),
        )
        render_section_title("品種画像", f"{len(ordered_images)}枚登録")
        render_image_gallery(ordered_images, "variety")
    else:
        render_surface("画像はまだ登録されていません。", title="品種画像", tone="soft")

    with st.expander("その他の操作", expanded=False):
        st.caption("削除後も「削除済み」セクションから復元できます。")
        delete_confirmed = st.checkbox(
            "この品種を削除することを確認しました",
            key=f"confirm_delete_variety_{selected_id}",
        )
        if st.button(
            "この品種を削除",
            key=f"delete_variety_{selected_id}",
            use_container_width=True,
            type="secondary",
            disabled=not delete_confirmed,
        ):
            soft_delete_variety(selected_id)
            st.session_state["variety_selected_from_list"] = ""
            if mobile_client:
                st.session_state["variety_mobile_panel"] = "list"
            st.success("削除しました。")
            st.rerun()


st.set_page_config(page_title="品種管理", layout="wide")
require_admin_session()
inject_app_style()
render_sidebar(active_page="varieties")
render_primary_nav(active_page="varieties")
mobile_client = is_mobile_client()
if mobile_client:
    render_page_header("品種管理", "一覧から品種を開き、必要な更新や復元を行います。")
else:
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


def _render_variety_section_switcher(*, mobile_client: bool) -> str:
    default_section = str(st.session_state.get("variety_active_section") or _VARIETY_SECTION_ORDER[0])
    if default_section not in _VARIETY_SECTION_ORDER:
        default_section = _VARIETY_SECTION_ORDER[0]
    with st.container(border=True):
        render_section_title("表示セクション", None if mobile_client else "必要なセクションだけ読み込みます。")
        if mobile_client:
            active_section = st.selectbox(
                "表示セクション",
                _VARIETY_SECTION_ORDER,
                index=_VARIETY_SECTION_ORDER.index(default_section),
                key="variety_active_section",
            )
        else:
            active_section = st.radio(
                "表示セクション",
                _VARIETY_SECTION_ORDER,
                index=_VARIETY_SECTION_ORDER.index(default_section),
                horizontal=True,
                key="variety_active_section",
            )
    return active_section


def _render_variety_list_section(*, mobile_client: bool) -> None:
    render_section_title("品種一覧", "フィルタで絞り込み、一覧から詳細へ進みます。")
    keyword, prefecture, discovery_filter = _render_variety_filters(mobile_client=mobile_client)

    if "variety_selected_from_list" not in st.session_state:
        st.session_state["variety_selected_from_list"] = ""
    if "variety_mobile_panel" not in st.session_state:
        st.session_state["variety_mobile_panel"] = "list"

    preselected = st.session_state.pop("selected_variety_id", "")
    if preselected:
        st.session_state["variety_selected_from_list"] = preselected
        if mobile_client:
            st.session_state["variety_mobile_panel"] = "detail"

    if mobile_client:
        render_view_transition_layer(
            "varieties-mobile-list-detail",
            current_state=str(st.session_state.get("variety_mobile_panel", "list") or "list"),
            enabled=True,
            mobile_only=True,
        )

    rows, total = list_varieties_for_list_tab(
        keyword=keyword or None,
        prefecture=prefecture or None,
    )

    selected_id = st.session_state.get("variety_selected_from_list", "")
    count_targets = [row["id"] for row in rows]
    if selected_id and selected_id not in count_targets:
        count_targets.append(selected_id)
    review_counts = get_review_counts_for_varieties(count_targets)
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

    if selected_id and not any(row["id"] == selected_id for row in visible_rows):
        selected_id = visible_rows[0]["id"] if visible_rows else ""
        st.session_state["variety_selected_from_list"] = selected_id
        if mobile_client and not selected_id:
            st.session_state["variety_mobile_panel"] = "list"

    mobile_panel = st.session_state.get("variety_mobile_panel", "list") if mobile_client else "split"
    if mobile_client and mobile_panel == "detail" and selected_id:
        discovered_targets = [selected_id] if int(review_counts.get(selected_id, 0)) > 0 else []
    else:
        discovered_targets = [row["id"] for row in visible_rows if int(review_counts.get(row["id"], 0)) > 0]
        if selected_id and int(review_counts.get(selected_id, 0)) > 0 and selected_id not in discovered_targets:
            discovered_targets.append(selected_id)
    primary_images = (
        list_primary_variety_images_with_signed_urls(discovered_targets)
        if discovered_targets
        else {}
    )
    latest_reviews = (
        get_latest_review_summary_for_varieties(discovered_targets)
        if discovered_targets
        else {}
    )

    if mobile_client:
        if mobile_panel == "detail" and selected_id:
            render_section_title("品種詳細", "一覧に戻って別の品種を選択できます。")
            render_view_transition_trigger(
                "varieties-mobile-list-detail",
                "detail-to-list",
                shared_key=selected_id,
                shared_role="target",
            )
            if st.button("← 一覧に戻る", key="variety_mobile_back", use_container_width=True):
                st.session_state["variety_mobile_panel"] = "list"
                st.rerun()
            discovered = review_counts.get(selected_id, 0) > 0
            _render_variety_detail_panel(
                selected_id,
                discovered=discovered,
                review_count=int(review_counts.get(selected_id, 0)),
                latest_review=latest_reviews.get(selected_id),
                primary_image=primary_images.get(selected_id),
                mobile_client=True,
            )
        else:
            st.session_state["variety_mobile_panel"] = "list"
            render_section_title("一覧", f"表示件数: {len(visible_rows)}件 / 全体: {total}件")
            if visible_rows:
                discovered_rows = [row for row in visible_rows if int(review_counts.get(row["id"], 0)) > 0]
                if discovered_rows:
                    quick_jump_options = [""] + [str(row["id"]) for row in discovered_rows[:50]]
                    quick_jump_id = st.selectbox(
                        "図鑑クイックジャンプ（発見済み）",
                        quick_jump_options,
                        format_func=lambda x: (
                            "選択してください"
                            if not x
                            else _clean_text(next((row.get("name") for row in discovered_rows if str(row["id"]) == str(x)), "")) or str(x)
                        ),
                        key="variety_mobile_quick_jump",
                    )
                    render_view_transition_trigger(
                        "varieties-mobile-list-detail",
                        "list-to-detail",
                        shared_key=quick_jump_id or None,
                        shared_role="source",
                    )
                    if quick_jump_id and st.button("選択品種を開く", key="variety_mobile_jump_open", use_container_width=True):
                        st.session_state["variety_selected_from_list"] = str(quick_jump_id)
                        st.session_state["variety_mobile_panel"] = "detail"
                        st.rerun()
                selected_from_cards = _render_mobile_variety_cards(
                    visible_rows,
                    review_counts,
                    primary_images,
                    latest_reviews,
                )
                if selected_from_cards:
                    st.session_state["variety_selected_from_list"] = str(selected_from_cards)
                    st.session_state["variety_mobile_panel"] = "detail"
                    st.rerun()
            else:
                render_empty_state(
                    "条件に一致する品種がありません。",
                    title="表示できる品種がありません",
                    hint="キーワードや都道府県条件を調整してください。",
                )
    else:
        list_col, detail_col = st.columns([1.4, 1], gap="large")
        with list_col:
            render_section_title("一覧", f"表示件数: {len(visible_rows)}件 / 全体: {total}件")
            if visible_rows:
                for row in visible_rows:
                    review_count = int(review_counts.get(row["id"], 0))
                    if _render_variety_list_item(
                        row,
                        review_count,
                        key_prefix="variety_open",
                        primary_image=primary_images.get(row["id"]),
                        latest_review=latest_reviews.get(row["id"]),
                    ):
                        selected_id = row["id"]
                        st.session_state["variety_selected_from_list"] = selected_id
            else:
                render_empty_state(
                    "条件に一致する品種がありません。",
                    title="表示できる品種がありません",
                    hint="キーワードや都道府県条件を調整してください。",
                )

        with detail_col:
            if selected_id:
                discovered = review_counts.get(selected_id, 0) > 0
                _render_variety_detail_panel(
                    selected_id,
                    discovered=discovered,
                    review_count=int(review_counts.get(selected_id, 0)),
                    latest_review=latest_reviews.get(selected_id),
                    primary_image=primary_images.get(selected_id),
                    mobile_client=False,
                )
            else:
                render_empty_state("一覧から品種を選択すると詳細が表示されます。", title="品種未選択")


def _render_variety_edit_section() -> None:
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
        prefecture_options = [""] + PREFECTURES
        acidity_options = [x.value for x in AcidityLevel]
        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input("品種名*", value=base.get("name", ""))
            alias_names = comma_values_input("別名 (カンマ区切り)", "alias_names_input", 20, 50)
            origin_prefecture = st.selectbox(
                "都道府県",
                prefecture_options,
                index=_resolve_select_index(prefecture_options, base.get("origin_prefecture", "")),
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
                acidity_options,
                index=_resolve_select_index(acidity_options, base.get("acidity_level", "unknown")),
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
        save = st.form_submit_button("保存", use_container_width=True, type="primary")

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
        if primary_image_id and st.button("メイン画像を設定", use_container_width=True, type="secondary"):
            set_primary_variety_image(edit_id, primary_image_id)
            st.success("メイン画像を更新しました。")
            st.rerun()


def _render_variety_deleted_section() -> None:
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
    if st.button("選択した品種を復元", use_container_width=True, disabled=not restore_id, type="primary"):
        try:
            restore_variety(restore_id)
            st.success("復元しました。")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


active_section = _render_variety_section_switcher(mobile_client=mobile_client)
if active_section == "一覧":
    _render_variety_list_section(mobile_client=mobile_client)
elif active_section == "作成・編集":
    _render_variety_edit_section()
else:
    _render_variety_deleted_section()
