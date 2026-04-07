from __future__ import annotations

from contextlib import nullcontext
import re

from src.components import layout


def test_inject_app_style_does_not_hide_sidebar_controls_for_desktop(monkeypatch) -> None:
    captured: dict[str, str | None] = {"html": None}

    monkeypatch.setattr(layout, "_should_hide_host_chrome", lambda: True)
    monkeypatch.setattr(layout, "is_mobile_client", lambda: False)
    monkeypatch.setattr(layout, "_inject_native_shell_bootstrap", lambda: None)
    monkeypatch.setattr(layout, "inject_offline_runtime", lambda: None)
    monkeypatch.setattr(
        layout.st,
        "markdown",
        lambda html, **_kwargs: captured.__setitem__("html", html),
    )

    layout.inject_app_style()

    assert captured["html"] is not None
    assert '[data-testid="stSidebarNav"]' not in captured["html"]
    assert '[data-testid="collapsedControl"]' not in captured["html"]
    assert '[data-testid="stSidebarCollapsedControl"]' not in captured["html"]
    assert '[data-testid="stSidebarCollapseButton"]' not in captured["html"]
    assert '[data-testid="stSidebar"] {\n            display: none !important;\n        }' not in captured["html"]
    assert 'header[data-testid="stHeader"]' in captured["html"]
    assert '.sl-desktop-nav-toggle-anchor' in captured["html"]


def test_inject_app_style_hides_sidebar_only_for_mobile(monkeypatch) -> None:
    captured: dict[str, str | None] = {"html": None}

    monkeypatch.setattr(layout, "_should_hide_host_chrome", lambda: True)
    monkeypatch.setattr(layout, "is_mobile_client", lambda: True)
    monkeypatch.setattr(layout, "_inject_native_shell_bootstrap", lambda: None)
    monkeypatch.setattr(layout, "inject_offline_runtime", lambda: None)
    monkeypatch.setattr(
        layout.st,
        "markdown",
        lambda html, **_kwargs: captured.__setitem__("html", html),
    )

    layout.inject_app_style()

    assert captured["html"] is not None
    assert re.search(
        r'@media \(max-width: 820px\).*?\[data-testid="stSidebar"] \{\s*display: none !important;',
        captured["html"],
        re.S,
    )
    assert 'button[kind="headerNoPadding"]' in captured["html"]


def test_native_shell_bootstrap_registers_service_worker_with_static_scope_only(monkeypatch) -> None:
    captured: dict[str, str | None] = {"html": None}

    monkeypatch.setattr(
        layout.components,
        "html",
        lambda html, **_kwargs: captured.__setitem__("html", html),
    )

    layout._inject_native_shell_bootstrap()

    assert captured["html"] is not None
    assert "resolveAppScopePath" not in captured["html"]
    assert "const scopeCandidates = [fallbackScope];" in captured["html"]


def test_render_surface_does_not_mark_accent_tone_as_important(monkeypatch) -> None:
    badge_calls: list[tuple[str, str, str | None]] = []

    monkeypatch.setattr(layout.st, "container", lambda **_kwargs: nullcontext())
    monkeypatch.setattr(layout.st, "markdown", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(layout.st, "caption", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        layout,
        "render_status_badge",
        lambda label, tone="neutral", *, icon=None: badge_calls.append((label, tone, icon)) or label,
    )

    layout.render_surface("Body", title="Accent surface", tone="accent")

    assert badge_calls == []


def test_render_section_switcher_renders_active_desktop_pill(monkeypatch) -> None:
    markdown_calls: list[str] = []
    button_calls: list[str] = []
    button_keys: list[str] = []

    class _DummyColumn:
        def __enter__(self) -> None:
            return None

        def __exit__(self, *_args: object) -> bool:
            return False

    monkeypatch.setattr(layout.st, "session_state", {"section_key": "一覧"})
    monkeypatch.setattr(layout, "is_mobile_client", lambda: False)
    monkeypatch.setattr(layout.st, "container", lambda **_kwargs: nullcontext())
    monkeypatch.setattr(layout, "render_section_title", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        layout.st,
        "columns",
        lambda count, gap=None: [_DummyColumn() for _ in range(count)],
    )
    monkeypatch.setattr(layout.st, "markdown", lambda html, **_kwargs: markdown_calls.append(html))
    monkeypatch.setattr(
        layout.st,
        "button",
        lambda label, **kwargs: button_calls.append(label) or button_keys.append(str(kwargs.get("key"))) or False,
    )

    selected = layout.render_section_switcher(["一覧", "作成・編集"], key="section_key")

    assert selected == "一覧"
    assert any("sl-segmented-control-active" in html for html in markdown_calls)
    assert button_calls == ["作成・編集"]
    assert button_keys == ["section_key__option__1"]


def test_render_section_switcher_uses_unique_keys_for_non_ascii_options(monkeypatch) -> None:
    button_keys: list[str] = []

    class _DummyColumn:
        def __enter__(self) -> None:
            return None

        def __exit__(self, *_args: object) -> bool:
            return False

    monkeypatch.setattr(layout.st, "session_state", {"section_key": "一覧"})
    monkeypatch.setattr(layout, "is_mobile_client", lambda: False)
    monkeypatch.setattr(layout.st, "container", lambda **_kwargs: nullcontext())
    monkeypatch.setattr(layout, "render_section_title", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        layout.st,
        "columns",
        lambda count, gap=None: [_DummyColumn() for _ in range(count)],
    )
    monkeypatch.setattr(layout.st, "markdown", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        layout.st,
        "button",
        lambda _label, **kwargs: button_keys.append(str(kwargs.get("key"))) or False,
    )

    layout.render_section_switcher(["一覧", "作成・編集", "削除済み"], key="section_key")

    assert button_keys == ["section_key__option__1", "section_key__option__2"]
