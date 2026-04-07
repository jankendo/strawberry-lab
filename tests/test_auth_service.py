from __future__ import annotations

import sys
from types import SimpleNamespace

import streamlit.runtime.scriptrunner as scriptrunner
import pytest

from src.services import auth_service


def _reset_cookie_manager_cache() -> None:
    auth_service._COOKIE_MANAGER_RUN_CACHE.update(
        {
            "session_id": None,
            "run_context": None,
            "secret": None,
            "is_ephemeral": None,
            "manager": None,
            "status": None,
        }
    )


def test_get_script_run_cache_identity_stays_stable_when_cursors_are_replaced(monkeypatch) -> None:
    widget_ids_this_run: set[str] = set()
    context = SimpleNamespace(
        session_id="session-1",
        page_script_hash="page-1",
        active_script_hash="page-1",
        widget_ids_this_run=widget_ids_this_run,
        cursors={0: "first"},
    )
    monkeypatch.setattr(scriptrunner, "get_script_run_ctx", lambda: context)

    first = auth_service._get_script_run_cache_identity()
    context.cursors = {1: "second"}
    second = auth_service._get_script_run_cache_identity()

    assert first == second


def test_get_cookie_manager_with_status_reuses_manager_when_cursors_change(monkeypatch) -> None:
    widget_ids_this_run: set[str] = set()
    context = SimpleNamespace(
        session_id="session-1",
        page_script_hash="page-1",
        active_script_hash="page-1",
        widget_ids_this_run=widget_ids_this_run,
        cursors={0: "first"},
    )
    created_managers: list[object] = []

    class _FakeEncryptedCookieManager:
        def __init__(self, *, prefix: str, password: str):
            self.prefix = prefix
            self.password = password
            created_managers.append(self)

        def ready(self) -> bool:
            return True

    _reset_cookie_manager_cache()
    monkeypatch.setattr(auth_service, "_get_cookie_secret", lambda: ("secret-value", False))
    monkeypatch.setattr(scriptrunner, "get_script_run_ctx", lambda: context)
    monkeypatch.setitem(
        sys.modules,
        "streamlit_cookies_manager",
        SimpleNamespace(EncryptedCookieManager=_FakeEncryptedCookieManager),
    )

    first_manager, first_status = auth_service._get_cookie_manager_with_status()
    context.cursors = {1: "second"}
    second_manager, second_status = auth_service._get_cookie_manager_with_status()

    assert len(created_managers) == 1
    assert first_manager is second_manager
    assert first_status == auth_service.AUTH_PERSISTENCE_READY
    assert second_status == auth_service.AUTH_PERSISTENCE_READY


def test_restore_login_from_cookie_returns_pending_when_cookie_manager_is_not_ready(monkeypatch) -> None:
    monkeypatch.setattr(auth_service.st, "session_state", {})
    monkeypatch.setattr(
        auth_service,
        "_read_auth_cookie_with_status",
        lambda: (None, auth_service.AUTH_PERSISTENCE_MANAGER_NOT_READY),
    )

    restored = auth_service.restore_login_from_cookie()

    assert restored is None
    assert auth_service.st.session_state[auth_service.AUTH_COOKIE_SYNC_PENDING_KEY] is True


def test_require_admin_session_stops_while_cookie_restore_is_pending(monkeypatch) -> None:
    class _StopCalled(Exception):
        pass

    switch_calls: list[str] = []
    info_calls: list[str] = []

    monkeypatch.setattr(
        auth_service.st,
        "session_state",
        {"is_authenticated": False, "current_user": None},
    )
    monkeypatch.setattr(auth_service, "initialize_auth_state", lambda: None)
    monkeypatch.setattr(auth_service, "restore_login_from_cookie", lambda: None)
    monkeypatch.setattr(auth_service.st, "switch_page", lambda page: switch_calls.append(page))
    monkeypatch.setattr(auth_service.st, "info", lambda message: info_calls.append(message))
    monkeypatch.setattr(auth_service.st, "stop", lambda: (_ for _ in ()).throw(_StopCalled()))

    with pytest.raises(_StopCalled):
        auth_service.require_admin_session()

    assert switch_calls == []
    assert info_calls == ["ログイン状態を復元しています。数秒後に自動で続行します。"]
