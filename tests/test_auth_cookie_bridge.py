from __future__ import annotations

from src.components import auth_cookie_bridge


def test_render_auth_cookie_bridge_if_needed_renders_cookie_script(monkeypatch) -> None:
    captured: dict[str, str | None] = {"html": None}
    monkeypatch.setattr(
        auth_cookie_bridge,
        "get_pending_auth_cookie_action",
        lambda: {
            "id": "action-1",
            "type": "set",
            "cookie_name": "remember_auth_v1",
            "cookie_value": "signed-cookie",
            "expires_at": 4_102_444_800,
        },
    )
    monkeypatch.setattr(
        auth_cookie_bridge.components,
        "html",
        lambda html, **_kwargs: captured.__setitem__("html", html),
    )

    auth_cookie_bridge.render_auth_cookie_bridge_if_needed()

    assert captured["html"] is not None
    assert "doc.cookie" in captured["html"]
    assert "location.reload" in captured["html"]
    assert '"type": "set"' in captured["html"]


def test_render_auth_cookie_bridge_if_needed_skips_without_action(monkeypatch) -> None:
    html_calls: list[str] = []
    monkeypatch.setattr(auth_cookie_bridge, "get_pending_auth_cookie_action", lambda: None)
    monkeypatch.setattr(
        auth_cookie_bridge.components,
        "html",
        lambda html, **_kwargs: html_calls.append(html),
    )

    auth_cookie_bridge.render_auth_cookie_bridge_if_needed()

    assert html_calls == []
