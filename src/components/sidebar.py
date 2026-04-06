"""Sidebar and primary navigation components."""

from __future__ import annotations

import streamlit as st

from src.constants.ui import APP_NAME
from src.services.auth_service import logout_user

_SIDEBAR_NAV_ITEMS: list[tuple[str, str, str, str]] = [
    ("dashboard", "Home.py", "ダッシュボード", "🏠"),
    ("varieties", "pages/01_varieties.py", "品種管理", "🍓"),
    ("reviews", "pages/02_reviews.py", "試食評価", "📝"),
    ("analytics", "pages/03_analytics.py", "分析", "📊"),
    ("pedigree", "pages/04_pedigree.py", "交配図", "🧬"),
    ("notes", "pages/06_notes.py", "研究メモ", "📓"),
    ("settings", "pages/07_settings.py", "設定", "⚙️"),
]
_MOBILE_TAB_ITEMS: list[tuple[str, str, str, str]] = [
    ("dashboard", "Home.py", "ダッシュボード", "🏠"),
    ("varieties", "pages/01_varieties.py", "品種管理", "🍓"),
    ("reviews", "pages/02_reviews.py", "試食評価", "📝"),
    ("analytics", "pages/03_analytics.py", "分析", "📊"),
    ("more", "pages/07_settings.py", "その他", "⋯"),
]
_CORE_TAB_KEYS = {tab_key for tab_key, _, _, _ in _MOBILE_TAB_ITEMS if tab_key != "more"}
_MORE_PAGE_KEYS = {"pedigree", "notes", "settings"}


def _resolve_mobile_active_tab(active_page: str) -> str:
    return active_page if active_page in _CORE_TAB_KEYS else "more"


def _render_mobile_tab(
    tab_key: str,
    tab_path: str,
    tab_label: str,
    tab_icon: str,
    *,
    active_tab: str,
    active_page: str,
) -> None:
    if tab_key == active_tab and not (tab_key == "more" and active_page in _MORE_PAGE_KEYS and active_page != "settings"):
        st.markdown(
            (
                '<div class="sl-bottom-nav-tab-active">'
                f'<span class="sl-bottom-nav-icon">{tab_icon}</span>'
                f'<span class="sl-bottom-nav-label">{tab_label}</span>'
                "</div>"
            ),
            unsafe_allow_html=True,
        )
        return

    button_kind = "primary" if tab_key == "more" and active_page in _MORE_PAGE_KEYS and active_page != "settings" else "secondary"
    if st.button(
        f"{tab_icon}\n{tab_label}",
        key=f"mobile_bottom_nav_{active_page}_{tab_key}",
        use_container_width=True,
        type=button_kind,
    ):
        st.switch_page(tab_path)


def render_primary_nav(*, active_page: str) -> None:
    """Render fixed bottom-tab navigation for mobile contexts."""
    if not st.session_state.get("is_authenticated"):
        return

    active_tab = _resolve_mobile_active_tab(active_page)
    st.markdown('<div class="sl-bottom-nav-anchor" aria-hidden="true"></div>', unsafe_allow_html=True)
    columns = st.columns(len(_MOBILE_TAB_ITEMS), gap="small")
    for col, (tab_key, tab_path, tab_label, tab_icon) in zip(columns, _MOBILE_TAB_ITEMS, strict=True):
        with col:
            _render_mobile_tab(
                tab_key,
                tab_path,
                tab_label,
                tab_icon,
                active_tab=active_tab,
                active_page=active_page,
            )


def render_sidebar(*, active_page: str) -> None:
    """Render desktop sidebar with explicit active navigation state."""
    with st.sidebar:
        st.markdown(
            f"""
            <div class="sl-sidebar-brand">
              <div class="sl-sidebar-brand-sub">テーマ</div>
              <div class="sl-sidebar-brand-title">🍓 イチゴ研究所</div>
              <div class="sl-sidebar-brand-sub">{APP_NAME}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.caption("ナビゲーション")
        for page_key, page_path, page_label, page_icon in _SIDEBAR_NAV_ITEMS:
            if page_key == active_page:
                st.markdown(
                    f'<div class="sl-sidebar-active">{page_icon} {page_label}</div>',
                    unsafe_allow_html=True,
                )
                continue
            st.page_link(page_path, label=f"{page_icon} {page_label}", use_container_width=True)

        with st.container(border=True):
            user = st.session_state.get("current_user")
            st.caption(f"ログイン中: {(user or {}).get('email', '-')}")
            if st.button("ログアウト", use_container_width=True, type="secondary", key="sidebar_logout"):
                logout_user()
