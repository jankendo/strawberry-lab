"""Reviews page."""

from __future__ import annotations

from datetime import date

import streamlit as st

from src.components.layout import inject_app_style, render_page_header, render_section_title
from src.components.pagination import render_pagination_controls
from src.components.sidebar import render_sidebar
from src.components.tables import render_table
from src.constants.ui import EMPTY_STATE_MESSAGE
from src.services.auth_service import require_admin_session
from src.services.review_service import create_or_update_review, list_reviews, restore_review, soft_delete_review
from src.services.storage_service import upload_review_image
from src.services.variety_service import list_active_varieties

st.set_page_config(page_title="試食評価", layout="wide")
require_admin_session()
inject_app_style()
render_sidebar()
render_page_header("試食評価", "試食記録の登録・履歴確認・復元を行います。")

tab_edit, tab_history, tab_deleted = st.tabs(["作成・編集", "履歴", "削除済み"])

with tab_edit:
    render_section_title("評価登録")
    varieties = list_active_varieties()
    if not varieties:
        st.info(EMPTY_STATE_MESSAGE)
    else:
        with st.form("review_form"):
            c1, c2 = st.columns(2)
            with c1:
                variety_id = st.selectbox(
                    "品種*",
                    [v["id"] for v in varieties],
                    format_func=lambda x: next(v["name"] for v in varieties if v["id"] == x),
                )
                tasted_date = st.date_input("試食日*", value=date.today(), max_value=date.today())
                purchase_place = st.text_input("購入場所")
                price_jpy = st.number_input("価格 (円)", min_value=0, max_value=1_000_000, value=0)
            with c2:
                sweetness = st.slider("甘味", 1, 5, 3)
                sourness = st.slider("酸味", 1, 5, 3)
                aroma = st.slider("香り", 1, 5, 3)
                texture = st.slider("食感", 1, 5, 3)
                appearance = st.slider("見た目", 1, 5, 3)
                overall = st.slider("総合", 1, 10, 5)
            comment = st.text_area("コメント", height=140)
            uploaded_files = st.file_uploader(
                "画像アップロード (最大3枚)",
                type=["jpg", "jpeg", "png", "webp"],
                accept_multiple_files=True,
            )
            submit = st.form_submit_button("保存", use_container_width=True)

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
            try:
                review_id, _ = create_or_update_review(payload)
                for file in uploaded_files[:3]:
                    upload_review_image(review_id, file.name, file.getvalue())
                st.success("保存しました。")
                st.rerun()
            except ValueError as exc:
                if str(exc) == "DUPLICATE_REVIEW":
                    if st.button("既存記録を更新する", use_container_width=True):
                        review_id, _ = create_or_update_review(payload, overwrite_duplicate=True)
                        for file in uploaded_files[:3]:
                            upload_review_image(review_id, file.name, file.getvalue())
                        st.success("既存記録を更新しました。")
                        st.rerun()
                else:
                    st.error(str(exc))
            except Exception as exc:
                st.error(str(exc))

with tab_history:
    render_section_title("評価履歴")
    varieties = list_active_varieties()
    f1, f2, f3 = st.columns(3)
    with f1:
        variety_filter = st.selectbox(
            "品種フィルタ",
            [""] + [v["id"] for v in varieties],
            format_func=lambda x: "すべて" if not x else next(v["name"] for v in varieties if v["id"] == x),
        )
    with f2:
        date_from = st.date_input("開始日", value=date.today().replace(day=1), key="reviews_from")
    with f3:
        date_to = st.date_input("終了日", value=date.today(), key="reviews_to")
    page, page_size = render_pagination_controls("reviews_history")
    rows, total = list_reviews(
        variety_id=variety_filter or None,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
    st.caption(f"合計: {total}件")
    render_table(rows)
    delete_id = st.selectbox(
        "削除対象",
        [""] + [r["id"] for r in rows],
        format_func=lambda x: next((f"{r['tasted_date']} {r['id'][:8]}" for r in rows if r["id"] == x), "未選択"),
    )
    if delete_id and st.button("削除する"):
        soft_delete_review(delete_id)
        st.success("削除しました。")
        st.rerun()

with tab_deleted:
    render_section_title("削除済みレビュー")
    page, page_size = render_pagination_controls("reviews_deleted")
    rows, _ = list_reviews(include_deleted=True, page=page, page_size=page_size)
    deleted_rows = [row for row in rows if row.get("deleted_at")]
    render_table(deleted_rows)
    restore_id = st.selectbox(
        "復元対象",
        [""] + [r["id"] for r in deleted_rows],
        format_func=lambda x: next((f"{r['tasted_date']} {r['id'][:8]}" for r in deleted_rows if r["id"] == x), "未選択"),
    )
    if restore_id and st.button("復元する", key="restore_review"):
        try:
            restore_review(restore_id)
            st.success("復元しました。")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
