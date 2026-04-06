"""Reviews page."""

from __future__ import annotations

from datetime import date

import streamlit as st

from src.components.layout import (
    inject_app_style,
    render_action_bar,
    render_empty_state,
    render_hero_banner,
    render_kpi_cards,
    render_section_title,
    render_status_badge,
    render_sticky_primary_action_anchor,
    render_surface,
)
from src.components.pagination import render_pagination_controls
from src.components.sidebar import render_primary_nav, render_sidebar
from src.components.tables import render_table
from src.constants.ui import EMPTY_STATE_MESSAGE
from src.services.auth_service import require_admin_session
from src.services.review_service import create_or_update_review, list_reviews, restore_review, soft_delete_review
from src.services.storage_service import upload_review_image
from src.services.variety_service import list_active_varieties
from src.utils.validation import normalize_review_tasted_date

_PENDING_DUPLICATE_PAYLOAD_KEY = "reviews_pending_duplicate_payload"
_PENDING_DUPLICATE_FILES_KEY = "reviews_pending_duplicate_files"
_SCORE_GUIDE_TEXT = "1=弱い / 3=普通 / 5=強い"
_SCORE_LEVEL_LABELS = {
    1: "弱い",
    2: "やや弱い",
    3: "普通",
    4: "やや強い",
    5: "強い",
}


def _variety_name_map(varieties: list[dict]) -> dict[str, str]:
    return {str(variety["id"]): str(variety.get("name") or variety["id"]) for variety in varieties}


def _collect_upload_files(uploaded_files) -> list[tuple[str, bytes]]:
    return [(uploaded.name, uploaded.getvalue()) for uploaded in (uploaded_files or [])[:3]]


def _upload_review_images(review_id: str, files_to_upload: list[tuple[str, bytes]]) -> None:
    for file_name, raw_bytes in files_to_upload:
        upload_review_image(review_id, file_name, raw_bytes)


def _clear_pending_duplicate() -> None:
    st.session_state.pop(_PENDING_DUPLICATE_PAYLOAD_KEY, None)
    st.session_state.pop(_PENDING_DUPLICATE_FILES_KEY, None)


def _normalize_pending_payload(payload: dict) -> dict:
    normalized_payload = payload.copy()
    normalized_payload["tasted_date"] = normalize_review_tasted_date(normalized_payload["tasted_date"])
    return normalized_payload


def _score_level_label(value: int) -> str:
    return _SCORE_LEVEL_LABELS.get(int(value), "普通")

st.set_page_config(page_title="試食評価", layout="wide")
require_admin_session()
inject_app_style()
render_sidebar(active_page="reviews")
render_primary_nav(active_page="reviews")
render_hero_banner(
    "試食評価",
    "登録・履歴確認・削除復元まで、試食レビュー運用を一画面で管理できます。",
    eyebrow="レビュー運用",
    chips=["日本語UI最適化", "重複上書き対応", "画像なし保存OK"],
)
render_action_bar(
    title="入力から運用までをシンプルに",
    description="必須入力は最小限、重複時は上書き確認付きで安全に保存します。",
    actions=["作成・編集", "履歴管理", "削除復元"],
)
active_varieties = list_active_varieties()

tab_edit, tab_history, tab_deleted = st.tabs(["レビュー登録", "履歴管理", "削除済み復元"])

with tab_edit:
    with st.container(border=True):
        render_section_title("評価登録", "必須項目を入力すると総合スコアを自動算出して保存できます。")
        varieties = active_varieties
        variety_names = _variety_name_map(varieties)
        if not varieties:
            render_empty_state(
                f"{EMPTY_STATE_MESSAGE} 先に「品種管理」で品種を登録してください。",
                title="品種が未登録です",
                action_label="🍓 品種管理を開く",
                action_path="pages/01_varieties.py",
            )
        else:
            with st.form("review_entry_form", clear_on_submit=False):
                st.caption("※ * は必須項目です。任意項目は空欄でも保存できます。")
                st.markdown("##### 1) 試食情報")
                variety_id = st.selectbox(
                    "品種 *",
                    [v["id"] for v in varieties],
                    format_func=lambda x: variety_names.get(str(x), str(x)),
                    key="review_variety_id",
                )
                tasted_date = st.date_input(
                    "試食日 *",
                    value=date.today(),
                    max_value=date.today(),
                    key="review_tasted_date",
                )
                purchase_place = st.text_input("購入場所", key="review_purchase_place")
                price_jpy = st.number_input(
                    "価格（円）",
                    min_value=0,
                    max_value=1_000_000,
                    value=0,
                    step=10,
                    key="review_price_jpy",
                )

                st.markdown("##### 2) 味覚スコア（必須）")
                st.caption(f"スコア目安: {_SCORE_GUIDE_TEXT}")
                sweetness = st.slider("甘味 *", 1, 5, 3, key="review_sweetness", help=_SCORE_GUIDE_TEXT)
                sourness = st.slider("酸味 *", 1, 5, 3, key="review_sourness", help=_SCORE_GUIDE_TEXT)
                aroma = st.slider("香り *", 1, 5, 3, key="review_aroma", help=_SCORE_GUIDE_TEXT)
                texture = st.slider("食感 *", 1, 5, 3, key="review_texture", help=_SCORE_GUIDE_TEXT)
                appearance = st.slider("見た目 *", 1, 5, 3, key="review_appearance", help=_SCORE_GUIDE_TEXT)
                st.caption(
                    "現在値: "
                    f"甘味 {sweetness}/5（{_score_level_label(sweetness)}）・"
                    f"酸味 {sourness}/5（{_score_level_label(sourness)}）・"
                    f"香り {aroma}/5（{_score_level_label(aroma)}）・"
                    f"食感 {texture}/5（{_score_level_label(texture)}）・"
                    f"見た目 {appearance}/5（{_score_level_label(appearance)}）"
                )
                overall = max(1, min(10, int(round((sweetness + sourness + aroma + texture + appearance) / 5 * 2))))
                render_kpi_cards([("総合スコア（自動）", f"{overall}/10", "5項目平均から算出")])

                st.markdown("##### 3) コメント・画像（任意）")
                comment = st.text_area("コメント", height=140, key="review_comment")
                uploaded_files = st.file_uploader(
                    "画像アップロード（最大3枚）",
                    type=["jpg", "jpeg", "png", "webp"],
                    accept_multiple_files=True,
                    key="review_uploaded_files",
                )
                current_upload_count = len(uploaded_files or [])
                if uploaded_files:
                    preview_targets = uploaded_files[:3]
                    st.image(
                        [file.getvalue() for file in preview_targets],
                        caption=[file.name for file in preview_targets],
                        use_container_width=True,
                    )

                selected_name = variety_names.get(str(variety_id), str(variety_id))
                render_surface(
                    f"品種: **{selected_name}** / "
                    f"試食日: **{tasted_date}** / "
                    f"総合スコア: **{overall}/10** / "
                    f"画像枚数: **{current_upload_count}枚**",
                    title="保存前サマリー",
                    subtitle="必須: 品種・試食日・5項目スコア",
                    tone="soft",
                )
                render_status_badge("任意項目（購入場所・価格・コメント・画像）は後から追記可能", tone="info")
                st.page_link("pages/01_varieties.py", label="🍓 品種情報を確認", use_container_width=True)
                render_sticky_primary_action_anchor("reviews-save")
                submit = st.form_submit_button("この内容で保存", use_container_width=True, type="primary")

            if submit:
                payload = {
                    "variety_id": variety_id,
                    "tasted_date": tasted_date,
                    "sweetness": sweetness,
                    "sourness": sourness,
                    "aroma": aroma,
                    "texture": texture,
                    "appearance": appearance,
                    "overall": overall,
                    "purchase_place": purchase_place,
                    "price_jpy": price_jpy,
                    "comment": comment,
                }
                files_to_upload = _collect_upload_files(uploaded_files)
                try:
                    review_id, _ = create_or_update_review(payload)
                    _upload_review_images(review_id, files_to_upload)
                    _clear_pending_duplicate()
                    st.success("保存しました。")
                    st.rerun()
                except ValueError as exc:
                    if str(exc) == "DUPLICATE_REVIEW":
                        st.session_state[_PENDING_DUPLICATE_PAYLOAD_KEY] = _normalize_pending_payload(payload)
                        st.session_state[_PENDING_DUPLICATE_FILES_KEY] = files_to_upload
                    else:
                        _clear_pending_duplicate()
                        st.error(str(exc))
                except Exception as exc:
                    _clear_pending_duplicate()
                    st.error(str(exc))

            pending_payload = st.session_state.get(_PENDING_DUPLICATE_PAYLOAD_KEY)
            if pending_payload:
                pending_variety = variety_names.get(
                    str(pending_payload["variety_id"]),
                    str(pending_payload["variety_id"]),
                )
                render_surface(
                    f"同じ品種・試食日のレビューが存在します（{pending_variety} / {pending_payload['tasted_date']}）。\n\n"
                    "上書き保存する場合は、確認チェック後に実行してください。",
                    title="重複レビューを検出しました",
                    tone="accent",
                )
                overwrite_confirm_key = (
                    f"confirm_overwrite_review_{pending_payload['variety_id']}_{pending_payload['tasted_date']}"
                )
                overwrite_confirmed = st.checkbox(
                    "既存記録を上書きすることを確認しました",
                    key=overwrite_confirm_key,
                )
                if st.button(
                    "既存記録を上書き保存する",
                    key="overwrite_review",
                    use_container_width=True,
                    type="secondary",
                    disabled=not overwrite_confirmed,
                ):
                    try:
                        review_id, _ = create_or_update_review(
                            pending_payload,
                            overwrite_duplicate=True,
                        )
                        _upload_review_images(
                            review_id,
                            st.session_state.get(_PENDING_DUPLICATE_FILES_KEY, []),
                        )
                        _clear_pending_duplicate()
                        st.success("既存記録を更新しました。")
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))
                if st.button(
                    "上書きを取り消す",
                    key="cancel_overwrite_review",
                    use_container_width=True,
                    type="secondary",
                ):
                    _clear_pending_duplicate()
                    st.info("上書きをキャンセルしました。")
                    st.rerun()

with tab_history:
    with st.container(border=True):
        render_section_title("評価履歴", "フィルタで絞り込み、内容確認や削除操作を行えます。")
        varieties = active_varieties
        variety_names = _variety_name_map(varieties)
        f1, f2, f3 = st.columns(3, gap="large")
        with f1:
            variety_filter = st.selectbox(
                "品種フィルタ",
                [""] + [v["id"] for v in varieties],
                format_func=lambda x: "すべて" if not x else variety_names.get(str(x), str(x)),
            )
        with f2:
            date_from = st.date_input("開始日", value=date.today().replace(day=1), key="reviews_from")
        with f3:
            date_to = st.date_input("終了日", value=date.today(), key="reviews_to")

    if date_from > date_to:
        st.error("開始日は終了日以前で指定してください。")
    else:
        page, page_size = render_pagination_controls("reviews_history")
        rows, total = list_reviews(
            variety_id=variety_filter or None,
            date_from=date_from,
            date_to=date_to,
            page=page,
            page_size=page_size,
        )
        with st.container(border=True):
            render_kpi_cards(
                [
                    ("ヒット件数", str(total), "検索条件に一致した総件数"),
                    ("現在ページ", str(len(rows)), f"{page_size}件表示設定"),
                ]
            )
            if rows:
                render_table(rows)
            else:
                render_empty_state(
                    "条件に一致するレビューはありません。",
                    title="検索結果がありません",
                    hint="フィルタを調整して再検索してください。",
                )

        with st.container(border=True):
            render_section_title("履歴アクション", "表示中のレビューから削除対象を選択します。")
            delete_col, delete_action_col = st.columns([2, 1], gap="medium")
            with delete_col:
                delete_id = st.selectbox(
                    "削除対象",
                    [""] + [r["id"] for r in rows],
                    format_func=lambda x: next(
                        (f"{r['tasted_date']} {r['id'][:8]}" for r in rows if r["id"] == x),
                        "未選択",
                    ),
                    key="reviews_delete_select",
                )
                delete_confirm_key = f"reviews_delete_confirm_{delete_id or 'none'}"
                delete_confirmed = st.checkbox(
                    "選択したレビューを削除することを確認しました",
                    key=delete_confirm_key,
                    disabled=not delete_id,
                )
            with delete_action_col:
                delete_clicked = st.button(
                    "選択したレビューを削除",
                    key="delete_review_action",
                    use_container_width=True,
                    disabled=not (delete_id and delete_confirmed),
                    type="secondary",
                )
        if delete_clicked:
            soft_delete_review(delete_id)
            st.success("削除しました。")
            st.rerun()

with tab_deleted:
    with st.container(border=True):
        render_section_title("削除済みレビュー", "復元可能なレビューを確認し、必要に応じて戻します。")
        page, page_size = render_pagination_controls("reviews_deleted")
        rows, _ = list_reviews(include_deleted=True, page=page, page_size=page_size)
        deleted_rows = [row for row in rows if row.get("deleted_at")]
        render_kpi_cards([("削除済み件数", str(len(deleted_rows)), "現在ページで表示中")])
        if deleted_rows:
            render_table(deleted_rows)
        else:
            render_empty_state("このページに削除済みレビューはありません。", title="復元対象がありません")

    with st.container(border=True):
        restore_col, restore_action_col = st.columns([2, 1], gap="medium")
        with restore_col:
            restore_id = st.selectbox(
                "復元対象",
                [""] + [r["id"] for r in deleted_rows],
                format_func=lambda x: next(
                    (f"{r['tasted_date']} {r['id'][:8]}" for r in deleted_rows if r["id"] == x),
                    "未選択",
                ),
                key="reviews_restore_select",
            )
        with restore_action_col:
            restore_clicked = st.button(
                "選択したレビューを復元",
                key="restore_review",
                use_container_width=True,
                disabled=not restore_id,
                type="primary",
            )
    if restore_clicked:
        try:
            restore_review(restore_id)
            st.success("復元しました。")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
