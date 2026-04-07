from __future__ import annotations

from contextlib import nullcontext

from src.components import sidebar
from src.components.sidebar import _resolve_mobile_active_tab


def test_resolve_mobile_active_tab_returns_core_tab_for_core_pages() -> None:
    assert _resolve_mobile_active_tab("dashboard") == "dashboard"
    assert _resolve_mobile_active_tab("reviews") == "reviews"


def test_resolve_mobile_active_tab_maps_settings_group_pages() -> None:
    assert _resolve_mobile_active_tab("pedigree") == "settings"
    assert _resolve_mobile_active_tab("settings") == "settings"
    assert _resolve_mobile_active_tab("unknown") == "settings"


def test_render_primary_nav_renders_for_mobile_authenticated_users(monkeypatch) -> None:
    markdown_calls: list[str] = []
    page_links: list[tuple[str, str]] = []

    class _DummyColumn:
        def __enter__(self) -> None:
            return None

        def __exit__(self, *_args: object) -> bool:
            return False

    monkeypatch.setattr(sidebar.st, "session_state", {"is_authenticated": True})
    monkeypatch.setattr(sidebar, "is_mobile_client", lambda: True)
    monkeypatch.setattr(sidebar.st, "markdown", lambda html, **_kwargs: markdown_calls.append(html))
    monkeypatch.setattr(
        sidebar.st,
        "columns",
        lambda count, gap=None: [_DummyColumn() for _ in range(count)],
    )
    monkeypatch.setattr(
        sidebar.st,
        "page_link",
        lambda path, label, **_kwargs: page_links.append((path, label)),
    )

    sidebar.render_primary_nav(active_page="dashboard")

    assert any("sl-bottom-nav-anchor" in html for html in markdown_calls)
    assert len(page_links) == len(sidebar._MOBILE_TAB_ITEMS) - 1


def test_render_primary_nav_skips_for_desktop_authenticated_users(monkeypatch) -> None:
    markdown_calls: list[str] = []
    page_links: list[tuple[str, str]] = []

    monkeypatch.setattr(sidebar.st, "session_state", {"is_authenticated": True})
    monkeypatch.setattr(sidebar, "is_mobile_client", lambda: False)
    monkeypatch.setattr(sidebar.st, "markdown", lambda html, **_kwargs: markdown_calls.append(html))
    monkeypatch.setattr(
        sidebar.st,
        "page_link",
        lambda path, label, **_kwargs: page_links.append((path, label)),
    )

    sidebar.render_primary_nav(active_page="dashboard")

    assert not markdown_calls
    assert not page_links


def test_render_sidebar_renders_for_desktop_authenticated_users(monkeypatch) -> None:
    markdown_calls: list[str] = []
    page_links: list[tuple[str, str]] = []
    captions: list[str] = []

    monkeypatch.setattr(
        sidebar.st,
        "session_state",
        {"is_authenticated": True, "current_user": {"email": "user@example.com"}},
    )
    monkeypatch.setattr(sidebar, "is_mobile_client", lambda: False)
    monkeypatch.setattr(sidebar.st, "sidebar", nullcontext())
    monkeypatch.setattr(sidebar.st, "container", lambda **_kwargs: nullcontext())
    monkeypatch.setattr(sidebar.st, "markdown", lambda html, **_kwargs: markdown_calls.append(html))
    monkeypatch.setattr(sidebar.st, "caption", lambda text, **_kwargs: captions.append(text))
    monkeypatch.setattr(
        sidebar.st,
        "page_link",
        lambda path, label, **_kwargs: page_links.append((path, label)),
    )
    monkeypatch.setattr(sidebar.st, "button", lambda *_args, **_kwargs: False)

    sidebar.render_sidebar(active_page="dashboard")

    assert any("sl-sidebar-brand" in html for html in markdown_calls)
    assert any("sl-sidebar-active" in html for html in markdown_calls)
    assert "ナビゲーション" in captions
    assert len(page_links) == len(sidebar._SIDEBAR_NAV_ITEMS) - 1


def test_render_sidebar_skips_for_mobile_authenticated_users(monkeypatch) -> None:
    markdown_calls: list[str] = []
    page_links: list[tuple[str, str]] = []

    monkeypatch.setattr(
        sidebar.st,
        "session_state",
        {"is_authenticated": True, "current_user": {"email": "user@example.com"}},
    )
    monkeypatch.setattr(sidebar, "is_mobile_client", lambda: True)
    monkeypatch.setattr(sidebar.st, "markdown", lambda html, **_kwargs: markdown_calls.append(html))
    monkeypatch.setattr(
        sidebar.st,
        "page_link",
        lambda path, label, **_kwargs: page_links.append((path, label)),
    )

    sidebar.render_sidebar(active_page="dashboard")

    assert not markdown_calls
    assert not page_links


def test_render_sidebar_renders_reopen_button_when_desktop_nav_is_collapsed(monkeypatch) -> None:
    markdown_calls: list[str] = []
    button_calls: list[str] = []

    monkeypatch.setattr(
        sidebar.st,
        "session_state",
        {
            "is_authenticated": True,
            "current_user": {"email": "user@example.com"},
            sidebar._DESKTOP_NAV_COLLAPSED_KEY: True,
        },
    )
    monkeypatch.setattr(sidebar, "is_mobile_client", lambda: False)
    monkeypatch.setattr(sidebar.st, "markdown", lambda html, **_kwargs: markdown_calls.append(html))
    monkeypatch.setattr(
        sidebar.st,
        "button",
        lambda label, **_kwargs: button_calls.append(label) or False,
    )

    sidebar.render_sidebar(active_page="dashboard")

    assert any('display: none !important' in html for html in markdown_calls)
    assert any("sl-desktop-nav-toggle-anchor" in html for html in markdown_calls)
    assert button_calls == ["☰ メニュー"]


def test_render_sidebar_uses_unique_close_button_keys_for_all_pages(monkeypatch) -> None:
    button_keys: list[str] = []

    monkeypatch.setattr(
        sidebar.st,
        "session_state",
        {"is_authenticated": True, "current_user": {"email": "user@example.com"}},
    )
    monkeypatch.setattr(sidebar, "is_mobile_client", lambda: False)
    monkeypatch.setattr(sidebar.st, "sidebar", nullcontext())
    monkeypatch.setattr(sidebar.st, "container", lambda **_kwargs: nullcontext())
    monkeypatch.setattr(sidebar.st, "markdown", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(sidebar.st, "caption", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(sidebar.st, "page_link", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        sidebar.st,
        "button",
        lambda _label, **kwargs: button_keys.append(str(kwargs.get("key"))) or False,
    )

    for page_key, *_rest in sidebar._SIDEBAR_NAV_ITEMS:
        sidebar.render_sidebar(active_page=page_key)

    close_keys = [key for key in button_keys if key.startswith("desktop_nav_close_")]
    assert close_keys == [f"desktop_nav_close_{page_key}" for page_key, *_rest in sidebar._SIDEBAR_NAV_ITEMS]


def test_render_sidebar_uses_unique_reopen_button_keys_for_all_pages(monkeypatch) -> None:
    button_keys: list[str] = []

    monkeypatch.setattr(
        sidebar.st,
        "session_state",
        {
            "is_authenticated": True,
            "current_user": {"email": "user@example.com"},
            sidebar._DESKTOP_NAV_COLLAPSED_KEY: True,
        },
    )
    monkeypatch.setattr(sidebar, "is_mobile_client", lambda: False)
    monkeypatch.setattr(sidebar.st, "markdown", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        sidebar.st,
        "button",
        lambda _label, **kwargs: button_keys.append(str(kwargs.get("key"))) or False,
    )

    for page_key, *_rest in sidebar._SIDEBAR_NAV_ITEMS:
        sidebar.render_sidebar(active_page=page_key)

    reopen_keys = [key for key in button_keys if key.startswith("desktop_nav_reopen_")]
    assert reopen_keys == [f"desktop_nav_reopen_{page_key}" for page_key, *_rest in sidebar._SIDEBAR_NAV_ITEMS]
