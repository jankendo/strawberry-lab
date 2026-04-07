"""Sidebar and primary navigation components."""

from __future__ import annotations

import json

import streamlit as st
import streamlit.components.v1 as components

from src.components.tables import is_mobile_client
from src.constants.ui import APP_NAME
from src.services.auth_service import logout_user

_DESKTOP_NAV_COLLAPSED_KEY = "_desktop_nav_collapsed"
_DESKTOP_NAV_COLLAPSED_PAGE_KEY = "_desktop_nav_collapsed_page"
_SIDEBAR_NAV_ITEMS: list[tuple[str, str, str, str]] = [
    ("dashboard", "Home.py", "ダッシュボード", "🏠"),
    ("varieties", "pages/01_varieties.py", "品種管理", "🍓"),
    ("reviews", "pages/02_reviews.py", "試食評価", "📝"),
    ("analytics", "pages/03_analytics.py", "分析", "📊"),
    ("pedigree", "pages/04_pedigree.py", "交配図", "🧬"),
    ("notes", "pages/06_notes.py", "研究メモ", "📓"),
    ("settings", "pages/07_settings.py", "設定", "⚙️"),
]
_MOBILE_TAB_ITEMS: list[tuple[str, str, str, str, str]] = [
    ("dashboard", "Home.py", "/", "ダッシュボード", "🏠"),
    ("varieties", "pages/01_varieties.py", "/varieties", "品種管理", "🍓"),
    ("reviews", "pages/02_reviews.py", "/reviews", "試食評価", "📝"),
    ("analytics", "pages/03_analytics.py", "/analytics", "分析", "📊"),
    ("settings", "pages/07_settings.py", "/settings", "設定", "⚙️"),
]
_CORE_TAB_KEYS = {tab_key for tab_key, _, _, _, _ in _MOBILE_TAB_ITEMS if tab_key != "settings"}
_SETTINGS_GROUP_PAGE_KEYS = {"pedigree", "notes", "settings"}


def _resolve_mobile_active_tab(active_page: str) -> str:
    if active_page in _CORE_TAB_KEYS:
        return active_page
    if active_page in _SETTINGS_GROUP_PAGE_KEYS:
        return "settings"
    return "settings"


def _is_desktop_nav_collapsed(*, active_page: str) -> bool:
    return bool(
        st.session_state.get(_DESKTOP_NAV_COLLAPSED_KEY, False)
        and st.session_state.get(_DESKTOP_NAV_COLLAPSED_PAGE_KEY) == active_page
    )


def _set_desktop_nav_collapsed(collapsed: bool, *, active_page: str | None = None) -> None:
    st.session_state[_DESKTOP_NAV_COLLAPSED_KEY] = collapsed
    if collapsed and active_page:
        st.session_state[_DESKTOP_NAV_COLLAPSED_PAGE_KEY] = active_page
    else:
        st.session_state.pop(_DESKTOP_NAV_COLLAPSED_PAGE_KEY, None)


def _render_desktop_nav_reopen_button(*, active_page: str) -> None:
    st.caption("メニューは閉じています。")
    if st.button("☰ メニューを開く", key=f"desktop_nav_reopen_{active_page}", type="secondary"):
        _set_desktop_nav_collapsed(False)
        st.rerun()


def _render_native_mobile_nav(*, active_tab: str, visible: bool) -> None:
    nav_config = {
        "visible": visible,
        "activeKey": active_tab,
        "items": [
            {
                "key": tab_key,
                "pathname": tab_pathname,
                "label": tab_label,
                "ariaLabel": f"{tab_label}に移動",
                "icon": tab_icon,
            }
            for tab_key, _tab_path, tab_pathname, tab_label, tab_icon in _MOBILE_TAB_ITEMS
        ],
    }
    config_json = json.dumps(nav_config, ensure_ascii=False)
    components.html(
        """
        <script>
        (function () {
          let parentWindow = null;
          try {
            parentWindow = window.parent;
          } catch (error) {
            console.warn("[native-shell] Unable to access parent window for nav shell:", error);
            return;
          }
          if (!parentWindow) {
            return;
          }
          const stateKey = "__slNativeShellState";
          const state = parentWindow[stateKey] || {};
          parentWindow[stateKey] = state;
          state.bottomNavConfig = __NAV_CONFIG__;
          if (typeof state.renderBottomNav === "function") {
            state.renderBottomNav(state.bottomNavConfig);
          }
        })();
        </script>
        """.replace("__NAV_CONFIG__", config_json),
        height=0,
    )


def render_primary_nav(*, active_page: str) -> None:
    """Render mobile navigation using a native-shell bottom bar."""
    visible = bool(st.session_state.get("is_authenticated") and is_mobile_client())
    active_tab = _resolve_mobile_active_tab(active_page) if visible else ""
    _render_native_mobile_nav(active_tab=active_tab, visible=visible)


def render_sidebar(*, active_page: str) -> None:
    """Render desktop sidebar with explicit active navigation state."""
    if not st.session_state.get("is_authenticated") or is_mobile_client():
        return

    if _is_desktop_nav_collapsed(active_page=active_page):
        st.markdown(
            """
            <style>
            [data-testid="stSidebar"] {
                display: none !important;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
        _render_desktop_nav_reopen_button(active_page=active_page)
        return

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
        if st.button("← メニューを閉じる", use_container_width=True, type="secondary", key=f"desktop_nav_close_{active_page}"):
            _set_desktop_nav_collapsed(True, active_page=active_page)
            st.rerun()
