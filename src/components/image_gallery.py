"""Image gallery rendering with signed URLs."""

from __future__ import annotations

import streamlit as st

from src.constants.ui import EMPTY_STATE_MESSAGE


def render_image_gallery(images: list[dict], key_prefix: str) -> None:
    """Render thumbnail gallery with per-image open button."""
    if not images:
        st.info(EMPTY_STATE_MESSAGE)
        return
    available_images = [image for image in images if str(image.get("signed_url") or "").strip()]
    if not available_images:
        st.info("画像を表示できません。ストレージ設定を確認してください。")
        return
    if len(available_images) != len(images):
        st.caption("一部の画像は表示できません。")
    columns = st.columns(3)
    for index, image in enumerate(available_images):
        with columns[index % 3]:
            st.image(image["signed_url"], caption=image.get("file_name") or "image", use_container_width=True)
            if st.button("Open", key=f"{key_prefix}_open_{image['id']}"):
                st.image(image["signed_url"], caption=image.get("file_name") or "image", use_container_width=True)
