from __future__ import annotations

from types import SimpleNamespace

from src.services import auth_service


def _set_request_cookies(monkeypatch, cookies: dict[str, str]) -> None:
    monkeypatch.setattr(auth_service.st, "context", SimpleNamespace(cookies=cookies), raising=False)


def test_serialize_and_deserialize_auth_cookie_round_trip(monkeypatch) -> None:
    monkeypatch.setattr(auth_service, "_get_cookie_secret", lambda: ("secret-value", False))

    raw_cookie = auth_service._serialize_auth_cookie(access_token="access-1", refresh_token="refresh-1", expires_at=4_102_444_800)

    assert raw_cookie is not None
    assert auth_service._deserialize_auth_cookie(raw_cookie) == {
        "access_token": "access-1",
        "refresh_token": "refresh-1",
        "expires_at": 4_102_444_800,
    }


def test_deserialize_auth_cookie_rejects_tampered_payload(monkeypatch) -> None:
    monkeypatch.setattr(auth_service, "_get_cookie_secret", lambda: ("secret-value", False))

    raw_cookie = auth_service._serialize_auth_cookie(access_token="access-1", refresh_token="refresh-1", expires_at=4_102_444_800)
    assert raw_cookie is not None
    tampered_cookie = raw_cookie[:-1] + ("A" if raw_cookie[-1] != "A" else "B")

    assert auth_service._deserialize_auth_cookie(tampered_cookie) is None


def test_ensure_auth_cookie_persistence_queues_set_action_when_request_cookie_is_missing(monkeypatch) -> None:
    session_state = {
        "is_authenticated": True,
        "current_user": {"id": "user-1", "email": "user@example.com"},
        "access_token": "access-1",
        "refresh_token": "refresh-1",
    }
    monkeypatch.setattr(auth_service.st, "session_state", session_state)
    monkeypatch.setattr(auth_service, "_get_cookie_secret", lambda: ("secret-value", False))
    _set_request_cookies(monkeypatch, {})

    saved = auth_service.ensure_auth_cookie_persistence()

    assert saved is False
    assert session_state[auth_service.AUTH_COOKIE_SYNC_PENDING_KEY] is True
    assert session_state[auth_service.AUTH_COOKIE_ACTION_KEY]["type"] == "set"
    assert session_state[auth_service.AUTH_COOKIE_ACTION_KEY]["storage_key"] == auth_service.AUTH_STORAGE_KEY
    assert session_state[auth_service.AUTH_COOKIE_ACTION_KEY]["max_age"] == auth_service.AUTH_COOKIE_TTL_SECONDS


def test_get_pending_auth_cookie_action_clears_set_action_when_cookie_matches(monkeypatch) -> None:
    monkeypatch.setattr(auth_service, "_get_cookie_secret", lambda: ("secret-value", False))
    expected_cookie = auth_service._serialize_auth_cookie(access_token="access-1", refresh_token="refresh-1", expires_at=4_102_444_800)
    assert expected_cookie is not None
    session_state = {
        auth_service.AUTH_COOKIE_ACTION_KEY: {
            "id": "action-1",
            "type": "set",
            "cookie_name": auth_service.AUTH_COOKIE_NAME,
            "cookie_value": expected_cookie,
            "expires_at": 4_102_444_800,
            "attempts": 0,
        },
        auth_service.AUTH_COOKIE_SYNC_PENDING_KEY: True,
    }
    monkeypatch.setattr(auth_service.st, "session_state", session_state)
    _set_request_cookies(monkeypatch, {auth_service.AUTH_COOKIE_NAME: expected_cookie})

    action = auth_service.get_pending_auth_cookie_action()

    assert action is None
    assert session_state[auth_service.AUTH_COOKIE_ACTION_KEY] is None
    assert session_state[auth_service.AUTH_COOKIE_SYNC_PENDING_KEY] is False


def test_get_pending_auth_cookie_action_keeps_set_action_available_until_request_cookie_matches(monkeypatch) -> None:
    session_state = {
        auth_service.AUTH_COOKIE_ACTION_KEY: {
            "id": "action-1",
            "type": "set",
            "cookie_name": auth_service.AUTH_COOKIE_NAME,
            "cookie_value": "signed-cookie",
            "expires_at": 4_102_444_800,
            "attempts": 2,
        },
        auth_service.AUTH_COOKIE_SYNC_PENDING_KEY: True,
        auth_service.AUTH_COOKIE_SYNC_ERROR_KEY: None,
    }
    monkeypatch.setattr(auth_service.st, "session_state", session_state)
    _set_request_cookies(monkeypatch, {})

    action = auth_service.get_pending_auth_cookie_action()

    assert action == session_state[auth_service.AUTH_COOKIE_ACTION_KEY]
    assert session_state[auth_service.AUTH_COOKIE_SYNC_PENDING_KEY] is True
    assert session_state[auth_service.AUTH_COOKIE_SYNC_ERROR_KEY] is None


def test_mark_auth_cookie_set_rendered_clears_blocking_state(monkeypatch) -> None:
    session_state = {
        auth_service.AUTH_COOKIE_ACTION_KEY: {
            "id": "action-1",
            "type": "set",
            "cookie_name": auth_service.AUTH_COOKIE_NAME,
            "cookie_value": "signed-cookie",
            "expires_at": 4_102_444_800,
            "attempts": 0,
        },
        auth_service.AUTH_COOKIE_SYNC_PENDING_KEY: True,
        auth_service.AUTH_COOKIE_SYNC_ERROR_KEY: None,
    }
    monkeypatch.setattr(auth_service.st, "session_state", session_state)

    auth_service.mark_auth_cookie_set_rendered("action-1")

    assert session_state[auth_service.AUTH_COOKIE_ACTION_KEY] is None
    assert session_state[auth_service.AUTH_COOKIE_SYNC_PENDING_KEY] is False
    assert session_state[auth_service.AUTH_COOKIE_SYNC_ERROR_KEY] is None


def test_restore_login_from_cookie_queues_clear_for_invalid_cookie(monkeypatch) -> None:
    session_state: dict[str, object] = {}
    monkeypatch.setattr(auth_service.st, "session_state", session_state)
    monkeypatch.setattr(auth_service, "_get_cookie_secret", lambda: ("secret-value", False))
    _set_request_cookies(monkeypatch, {auth_service.AUTH_COOKIE_NAME: "invalid-cookie"})

    restored = auth_service.restore_login_from_cookie()

    assert restored is False
    assert session_state[auth_service.AUTH_COOKIE_ACTION_KEY]["type"] == "clear"


def test_restore_login_from_cookie_restores_session_and_queues_cookie_refresh(monkeypatch) -> None:
    fake_user = SimpleNamespace(id="user-1", email="user@example.com")
    fake_session = SimpleNamespace(access_token="new-access", refresh_token="new-refresh")
    fake_auth_result = SimpleNamespace(user=fake_user, session=fake_session)
    fake_client = SimpleNamespace(
        auth=SimpleNamespace(
            set_session=lambda access_token, refresh_token: fake_auth_result,
            refresh_session=lambda refresh_token: fake_auth_result,
            sign_out=lambda: None,
        )
    )
    monkeypatch.setattr(auth_service, "_get_cookie_secret", lambda: ("secret-value", False))
    monkeypatch.setattr(auth_service, "_is_admin_user", lambda *, client, user_id: True)
    monkeypatch.setattr(auth_service, "get_anon_supabase_client", lambda: fake_client)
    old_cookie = auth_service._serialize_auth_cookie(access_token="old-access", refresh_token="old-refresh", expires_at=4_102_444_800)
    assert old_cookie is not None
    session_state: dict[str, object] = {}
    monkeypatch.setattr(auth_service.st, "session_state", session_state)
    _set_request_cookies(monkeypatch, {auth_service.AUTH_COOKIE_NAME: old_cookie})

    restored = auth_service.restore_login_from_cookie()

    assert restored is True
    assert session_state["is_authenticated"] is True
    assert session_state["current_user"] == {"id": "user-1", "email": "user@example.com"}
    assert session_state[auth_service.AUTH_COOKIE_SYNC_PENDING_KEY] is True
    assert session_state[auth_service.AUTH_COOKIE_ACTION_KEY]["type"] == "set"


def test_logout_user_queues_cookie_clear_before_switch_page(monkeypatch) -> None:
    sign_out_calls: list[str] = []
    switch_calls: list[str] = []
    fake_client = SimpleNamespace(auth=SimpleNamespace(sign_out=lambda: sign_out_calls.append("sign-out")))
    session_state = {
        "supabase_client_user": fake_client,
        "current_user": {"id": "user-1"},
        "is_authenticated": True,
        "access_token": "access-1",
        "refresh_token": "refresh-1",
    }
    monkeypatch.setattr(auth_service.st, "session_state", session_state)
    monkeypatch.setattr(auth_service.st, "switch_page", lambda page: switch_calls.append(page))
    _set_request_cookies(monkeypatch, {auth_service.AUTH_COOKIE_NAME: "signed-cookie"})

    auth_service.logout_user()

    assert sign_out_calls == ["sign-out"]
    assert switch_calls == ["Home.py"]
    assert session_state[auth_service.AUTH_COOKIE_ACTION_KEY]["type"] == "clear"
    assert "current_user" not in session_state


def test_ensure_public_access_session_seeds_public_client(monkeypatch) -> None:
    fake_client = SimpleNamespace(name="public-client")
    session_state: dict[str, object] = {}
    monkeypatch.setattr(auth_service.st, "session_state", session_state)
    monkeypatch.setattr(auth_service, "get_anon_supabase_client", lambda: fake_client)

    auth_service.ensure_public_access_session()

    assert session_state["is_authenticated"] is True
    assert session_state["current_user"] == auth_service.PUBLIC_ACCESS_USER
    assert session_state["supabase_client_user"] is fake_client


def test_get_user_client_falls_back_to_public_client(monkeypatch) -> None:
    fake_client = SimpleNamespace(name="public-client")
    session_state: dict[str, object] = {}
    monkeypatch.setattr(auth_service.st, "session_state", session_state)
    monkeypatch.setattr(auth_service, "get_anon_supabase_client", lambda: fake_client)

    client = auth_service.get_user_client()

    assert client is fake_client
    assert session_state["current_user"] == auth_service.PUBLIC_ACCESS_USER


def test_require_admin_session_keeps_public_mode_active(monkeypatch) -> None:
    fake_client = SimpleNamespace(name="public-client")
    session_state: dict[str, object] = {}
    monkeypatch.setattr(auth_service.st, "session_state", session_state)
    monkeypatch.setattr(auth_service, "get_anon_supabase_client", lambda: fake_client)

    auth_service.require_admin_session()

    assert session_state["is_authenticated"] is True
    assert session_state["current_user"] == auth_service.PUBLIC_ACCESS_USER
    assert session_state["supabase_client_user"] is fake_client
