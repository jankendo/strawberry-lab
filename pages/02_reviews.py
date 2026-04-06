"""Reviews page."""

from __future__ import annotations

from datetime import date

import streamlit as st

from src.components.layout import (
    inject_app_style,
    render_action_bar,
    render_hero_banner,
    render_info_card,
    render_kpi_cards,
    render_section_title,
)
from src.components.pagination import render_pagination_controls
from src.components.sidebar import render_sidebar
from src.components.tables import render_table
from src.constants.ui import EMPTY_STATE_MESSAGE
from src.services.auth_service import require_admin_session
from src.services.review_service import create_or_update_review, list_reviews, restore_review, soft_delete_review
from src.services.storage_service import upload_review_image
from src.services.variety_service import list_active_varieties
from src.utils.validation import normalize_review_tasted_date

_PENDING_DUPLICATE_PAYLOAD_KEY = "reviews_pending_duplicate_payload"
_PENDING_DUPLICATE_FILES_KEY = "reviews_pending_duplicate_files"


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


st.set_page_config(page_title="試食評価", layout="wide")
require_admin_session()
inject_app_style()
render_sidebar()
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

tab_edit, tab_history, tab_deleted = st.tabs(["レビュー登録", "履歴管理", "削除済み復元"])

with tab_edit:
    render_section_title("評価登録", "試食情報・スコア・コメントを入力して保存します。")
    varieties = list_active_varieties()
    variety_names = _variety_name_map(varieties)
    if not varieties:
        st.warning(f"{EMPTY_STATE_MESSAGE} 先に「品種管理」で品種を登録してください。")
    else:
        render_info_card(
            "<strong>保存ルール</strong><br>"
            "同じ品種・試食日のレビューがある場合は、確認後に上書き更新できます。<br>"
            "画像は任意で、未選択でも保存可能です。"
        )
        with st.form("review_form"):
            st.markdown("##### 1) 試食情報")
            c1, c2 = st.columns([1.2, 1])
            with c1:
                variety_id = st.selectbox(
                    "品種*",
                    [v["id"] for v in varieties],
                    format_func=lambda x: variety_names.get(str(x), str(x)),
                )
                tasted_date = st.date_input("試食日*", value=date.today(), max_value=date.today())
            with c2:
                purchase_place = st.text_input("購入場所")
                price_jpy = st.number_input("価格 (円)", min_value=0, max_value=1_000_000, value=0)

            st.markdown("##### 2) 味覚スコア")
            s1, s2, s3 = st.columns(3)
            with s1:
                sweetness = st.slider("甘味", 1, 5, 3)
                sourness = st.slider("酸味", 1, 5, 3)
            with s2:
                aroma = st.slider("香り", 1, 5, 3)
                texture = st.slider("食感", 1, 5, 3)
            with s3:
                appearance = st.slider("見た目", 1, 5, 3)
                overall = st.slider("総合", 1, 10, 5)

            st.markdown("##### 3) コメント・画像")
            comment = st.text_area("コメント", height=140)
            uploaded_files = st.file_uploader(
                "画像アップロード (最大3枚)",
                type=["jpg", "jpeg", "png", "webp"],
                accept_multiple_files=True,
            )
            st.caption("※ 画像は任意です。未選択でもレビュー保存できます。")
            submit = st.form_submit_button("この内容で保存", use_container_width=True)

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
            st.warning(
                f"同じ品種・試食日のレビューが存在します（{pending_variety} / {pending_payload['tasted_date']}）。"
                "上書き保存する場合は下のボタンを押してください。"
            )
            a1, a2 = st.columns([2, 1])
            with a1:
                if st.button("既存記録を上書き保存する", key="overwrite_review", use_container_width=True):
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
            with a2:
                if st.button("上書きを取り消す", key="cancel_overwrite_review", use_container_width=True):
                    _clear_pending_duplicate()
                    st.info("上書きをキャンセルしました。")
                    st.rerun()

with tab_history:
    render_section_title("評価履歴", "フィルタで絞り込み、内容確認や削除操作を行えます。")
    varieties = list_active_varieties()
    variety_names = _variety_name_map(varieties)
    f1, f2, f3 = st.columns(3)
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
        render_kpi_cards(
            [
                ("ヒット件数", str(total), "検索条件に一致した総件数"),
                ("現在ページ", str(len(rows)), f"{page_size}件表示設定"),
            ]
        )
        if rows:
            render_table(rows)
        else:
            st.info("条件に一致するレビューはありません。フィルタを調整して再検索してください。")

        render_section_title("履歴アクション", "表示中のレビューから削除対象を選択します。")
        delete_id = st.selectbox(
            "削除対象",
            [""] + [r["id"] for r in rows],
            format_func=lambda x: next(
                (f"{r['tasted_date']} {r['id'][:8]}" for r in rows if r["id"] == x),
                "未選択",
            ),
            key="reviews_delete_select",
        )
        if st.button(
            "選択したレビューを削除",
            key="delete_review_action",
            use_container_width=True,
            disabled=not delete_id,
        ):
            soft_delete_review(delete_id)
            st.success("削除しました。")
            st.rerun()

with tab_deleted:
    render_section_title("削除済みレビュー", "復元可能なレビューを確認し、必要に応じて戻します。")
    page, page_size = render_pagination_controls("reviews_deleted")
    rows, _ = list_reviews(include_deleted=True, page=page, page_size=page_size)
    deleted_rows = [row for row in rows if row.get("deleted_at")]
    render_kpi_cards([("削除済み件数", str(len(deleted_rows)), "現在ページで表示中")])
    if deleted_rows:
        render_table(deleted_rows)
    else:
        st.info("このページに削除済みレビューはありません。")
    restore_id = st.selectbox(
        "復元対象",
        [""] + [r["id"] for r in deleted_rows],
        format_func=lambda x: next(
            (f"{r['tasted_date']} {r['id'][:8]}" for r in deleted_rows if r["id"] == x),
            "未選択",
        ),
        key="reviews_restore_select",
    )
    if st.button(
        "選択したレビューを復元",
        key="restore_review",
        use_container_width=True,
        disabled=not restore_id,
    ):
        try:
            restore_review(restore_id)
            st.success("復元しました。")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
