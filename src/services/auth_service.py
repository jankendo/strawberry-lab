"""Authentication and authorization service."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from uuid import uuid4

import streamlit as st

from src.core.supabase_client import get_anon_supabase_client


AUTH_KEYS = ("current_user", "supabase_client_user", "is_authenticated", "access_token", "refresh_token", "admin_checked_at")
AUTH_COOKIE_NAME = "remember_auth_v1"
AUTH_COOKIE_TTL_DAYS = 30
AUTH_COOKIE_VERSION = 1
AUTH_COOKIE_SYNC_PENDING_KEY = "_auth_cookie_sync_pending"
AUTH_COOKIE_ACTION_KEY = "_auth_cookie_action"
AUTH_COOKIE_SYNC_ERROR_KEY = "_auth_cookie_sync_error"
AUTH_PERSISTENCE_READY = "ready"
AUTH_PERSISTENCE_READY_EPHEMERAL_SECRET = "ready_ephemeral_secret"
AUTH_PERSISTENCE_MISSING_SECRET = "missing_secret"
AUTH_PERSISTENCE_MANAGER_UNAVAILABLE = "cookie_manager_unavailable"
AUTH_PERSISTENCE_MANAGER_NOT_READY = "cookie_manager_not_ready"
AUTH_PERSISTENCE_MANAGER_NOT_READY_EPHEMERAL_SECRET = "cookie_manager_not_ready_ephemeral_secret"

_EPHEMERAL_COOKIE_SECRET: str | None = None


def initialize_auth_state() -> None:
    """Initialize auth session state keys."""
    for key in AUTH_KEYS:
        if key not in st.session_state:
            st.session_state[key] = None if key != "is_authenticated" else False
    if AUTH_COOKIE_SYNC_PENDING_KEY not in st.session_state:
        st.session_state[AUTH_COOKIE_SYNC_PENDING_KEY] = False
    if AUTH_COOKIE_ACTION_KEY not in st.session_state:
        st.session_state[AUTH_COOKIE_ACTION_KEY] = None
    if AUTH_COOKIE_SYNC_ERROR_KEY not in st.session_state:
        st.session_state[AUTH_COOKIE_SYNC_ERROR_KEY] = None


def _get_process_ephemeral_cookie_secret() -> str | None:
    global _EPHEMERAL_COOKIE_SECRET
    if _EPHEMERAL_COOKIE_SECRET:
        return _EPHEMERAL_COOKIE_SECRET
    try:
        _EPHEMERAL_COOKIE_SECRET = secrets.token_urlsafe(48)
    except Exception:
        return None
    return _EPHEMERAL_COOKIE_SECRET


def _get_cookie_secret() -> tuple[str | None, bool]:
    secret = os.getenv("APP_COOKIE_SECRET")
    if secret:
        return secret, False
    try:
        secret_from_secrets = st.secrets.get("APP_COOKIE_SECRET")
        if secret_from_secrets:
            return str(secret_from_secrets), False
    except Exception:
        pass

    ephemeral_secret = _get_process_ephemeral_cookie_secret()
    if ephemeral_secret:
        return ephemeral_secret, True
    return None, False


def _set_auth_cookie_sync_pending(pending: bool) -> None:
    initialize_auth_state()
    st.session_state[AUTH_COOKIE_SYNC_PENDING_KEY] = bool(pending)


def _set_auth_cookie_sync_error(message: str | None) -> None:
    initialize_auth_state()
    st.session_state[AUTH_COOKIE_SYNC_ERROR_KEY] = str(message).strip() if message else None


def get_auth_cookie_sync_error() -> str | None:
    initialize_auth_state()
    value = st.session_state.get(AUTH_COOKIE_SYNC_ERROR_KEY)
    return str(value).strip() if value else None


def _clear_auth_cookie_action() -> None:
    initialize_auth_state()
    st.session_state[AUTH_COOKIE_ACTION_KEY] = None


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value or "") + padding)


def _get_request_cookie_value(cookie_name: str) -> str | None:
    try:
        cookies = st.context.cookies
    except Exception:
        return None
    try:
        raw = cookies.get(cookie_name)
    except Exception:
        raw = None
    if raw is None:
        return None
    value = str(raw).strip()
    return value or None


def _sign_auth_cookie_body(body: str) -> str | None:
    secret, _is_ephemeral = _get_cookie_secret()
    if not secret:
        return None
    digest = hmac.new(secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).digest()
    return _base64url_encode(digest)


def _serialize_auth_cookie(*, access_token: str, refresh_token: str, expires_at: int | None = None) -> str | None:
    signature = _sign_auth_cookie_body("")
    if signature is None:
        return None
    normalized_expires_at = int(expires_at or (int(time.time()) + AUTH_COOKIE_TTL_DAYS * 24 * 60 * 60))
    payload = {
        "v": AUTH_COOKIE_VERSION,
        "access_token": str(access_token or ""),
        "refresh_token": str(refresh_token or ""),
        "expires_at": normalized_expires_at,
    }
    body = _base64url_encode(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    signed_body = _sign_auth_cookie_body(body)
    if not signed_body:
        return None
    return f"{body}.{signed_body}"


def _deserialize_auth_cookie(raw_value: str | None) -> dict | None:
    raw = str(raw_value or "").strip()
    if not raw or "." not in raw:
        return None
    body, provided_signature = raw.split(".", 1)
    expected_signature = _sign_auth_cookie_body(body)
    if not expected_signature or not hmac.compare_digest(provided_signature, expected_signature):
        return None
    try:
        payload = json.loads(_base64url_decode(body).decode("utf-8"))
    except Exception:
        return None
    try:
        expires_at = int(payload.get("expires_at") or 0)
    except Exception:
        return None
    if payload.get("v") != AUTH_COOKIE_VERSION or not expires_at or expires_at <= int(time.time()):
        return None
    access_token = str(payload.get("access_token") or "").strip()
    refresh_token = str(payload.get("refresh_token") or "").strip()
    if not access_token or not refresh_token:
        return None
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": expires_at,
    }


def _queue_auth_cookie_set(*, access_token: str, refresh_token: str) -> bool:
    initialize_auth_state()
    cookie_value = _serialize_auth_cookie(access_token=access_token, refresh_token=refresh_token)
    if not cookie_value:
        _clear_auth_cookie_action()
        _set_auth_cookie_sync_pending(False)
        _set_auth_cookie_sync_error("ログイン保持用の署名鍵を初期化できませんでした。")
        return False
    current_cookie = _get_request_cookie_value(AUTH_COOKIE_NAME)
    if current_cookie == cookie_value:
        _clear_auth_cookie_action()
        _set_auth_cookie_sync_pending(False)
        _set_auth_cookie_sync_error(None)
        return True
    existing_action = st.session_state.get(AUTH_COOKIE_ACTION_KEY)
    if (
        isinstance(existing_action, dict)
        and str(existing_action.get("type") or "") == "set"
        and str(existing_action.get("cookie_value") or "") == cookie_value
    ):
        _set_auth_cookie_sync_pending(True)
        _set_auth_cookie_sync_error(None)
        return False
    st.session_state[AUTH_COOKIE_ACTION_KEY] = {
        "id": str(uuid4()),
        "type": "set",
        "cookie_name": AUTH_COOKIE_NAME,
        "cookie_value": cookie_value,
        "expires_at": int(time.time()) + AUTH_COOKIE_TTL_DAYS * 24 * 60 * 60,
        "attempts": 0,
    }
    _set_auth_cookie_sync_pending(True)
    _set_auth_cookie_sync_error(None)
    return False


def _queue_auth_cookie_clear() -> None:
    initialize_auth_state()
    current_cookie = _get_request_cookie_value(AUTH_COOKIE_NAME)
    if not current_cookie:
        _clear_auth_cookie_action()
        _set_auth_cookie_sync_error(None)
        return
    existing_action = st.session_state.get(AUTH_COOKIE_ACTION_KEY)
    if isinstance(existing_action, dict) and str(existing_action.get("type") or "") == "clear":
        return
    st.session_state[AUTH_COOKIE_ACTION_KEY] = {
        "id": str(uuid4()),
        "type": "clear",
        "cookie_name": AUTH_COOKIE_NAME,
        "attempts": 0,
    }
    _set_auth_cookie_sync_error(None)


def get_pending_auth_cookie_action() -> dict | None:
    """Return a pending cookie bridge action when browser state needs syncing."""
    initialize_auth_state()
    action = st.session_state.get(AUTH_COOKIE_ACTION_KEY)
    if not isinstance(action, dict):
        return None

    current_cookie = _get_request_cookie_value(AUTH_COOKIE_NAME)
    action_type = str(action.get("type") or "")
    if action_type == "set":
        expected_cookie = str(action.get("cookie_value") or "")
        if expected_cookie and current_cookie == expected_cookie:
            _clear_auth_cookie_action()
            _set_auth_cookie_sync_pending(False)
            _set_auth_cookie_sync_error(None)
            return None
        _set_auth_cookie_sync_pending(True)
        _set_auth_cookie_sync_error(None)
        return dict(action)
    if action_type == "clear":
        if not current_cookie:
            _clear_auth_cookie_action()
            _set_auth_cookie_sync_error(None)
            return None
        attempts = int(action.get("attempts") or 0) + 1
        if attempts > 2:
            _clear_auth_cookie_action()
            return None
        next_action = dict(action)
        next_action["attempts"] = attempts
        st.session_state[AUTH_COOKIE_ACTION_KEY] = next_action
        return dict(next_action)
    _clear_auth_cookie_action()
    return None


def mark_auth_cookie_set_rendered(action_id: str | None) -> None:
    """Stop blocking the authenticated UI once the browser has received a set-cookie action."""
    initialize_auth_state()
    current_action = st.session_state.get(AUTH_COOKIE_ACTION_KEY)
    if not isinstance(current_action, dict):
        return
    if str(current_action.get("type") or "") != "set":
        return
    if str(current_action.get("id") or "") != str(action_id or ""):
        return
    _clear_auth_cookie_action()
    _set_auth_cookie_sync_pending(False)
    _set_auth_cookie_sync_error(None)


def _set_authenticated_state(*, client, user, access_token: str, refresh_token: str) -> None:
    st.session_state["current_user"] = {"id": user.id, "email": user.email}
    st.session_state["supabase_client_user"] = client
    st.session_state["is_authenticated"] = True
    st.session_state["access_token"] = access_token
    st.session_state["refresh_token"] = refresh_token
    st.session_state["admin_checked_at"] = int(time.time())


def get_auth_persistence_status() -> dict[str, str | bool]:
    """Return availability information for first-party auth-cookie persistence."""
    secret, is_ephemeral = _get_cookie_secret()
    if secret and not is_ephemeral:
        return {
            "available": True,
            "code": AUTH_PERSISTENCE_READY,
            "message": "30日ログイン保持は有効です。",
        }
    if secret and is_ephemeral:
        return {
            "available": True,
            "code": AUTH_PERSISTENCE_READY_EPHEMERAL_SECRET,
            "message": "APP_COOKIE_SECRET が未設定のため、一時ランダム秘密鍵でログイン保持を継続中です。再起動/再デプロイ時に保持がリセットされる場合があります。",
        }
    return {
        "available": False,
        "code": AUTH_PERSISTENCE_MISSING_SECRET,
        "message": "APP_COOKIE_SECRET が未設定で、一時秘密鍵の生成にも失敗したため、30日ログイン保持は無効です。",
    }


def ensure_auth_cookie_persistence() -> bool:
    """Queue browser sync until the current authenticated session is in a first-party cookie."""
    initialize_auth_state()
    if not st.session_state.get("is_authenticated") or not st.session_state.get("current_user"):
        _set_auth_cookie_sync_pending(False)
        return False

    access_token = str(st.session_state.get("access_token") or "").strip()
    refresh_token = str(st.session_state.get("refresh_token") or "").strip()
    if not access_token or not refresh_token:
        _set_auth_cookie_sync_pending(False)
        return False
    return _queue_auth_cookie_set(access_token=access_token, refresh_token=refresh_token)


def _is_admin_user(*, client, user_id: str) -> bool:
    admin = (
        client.table("app_users")
        .select("user_id,email,role")
        .eq("user_id", user_id)
        .eq("role", "admin")
        .maybe_single()
        .execute()
    )
    return bool(admin.data)


def login_user(email: str, password: str) -> None:
    """Login with Supabase Auth and enforce app_users admin membership."""
    initialize_auth_state()
    client = get_anon_supabase_client()
    result = client.auth.sign_in_with_password({"email": email, "password": password})
    if not result.user or not result.session:
        raise RuntimeError("ログインに失敗しました。")
    if not _is_admin_user(client=client, user_id=result.user.id):
        client.auth.sign_out()
        raise PermissionError("このアカウントは許可されていません。")
    _set_authenticated_state(
        client=client,
        user=result.user,
        access_token=result.session.access_token,
        refresh_token=result.session.refresh_token,
    )
    ensure_auth_cookie_persistence()


def is_auth_cookie_sync_pending() -> bool:
    initialize_auth_state()
    return bool(st.session_state.get(AUTH_COOKIE_SYNC_PENDING_KEY))


def restore_login_from_cookie() -> bool | None:
    """Restore login state from the first-party signed auth cookie when available."""
    initialize_auth_state()
    if st.session_state.get("is_authenticated") and st.session_state.get("current_user"):
        ensure_auth_cookie_persistence()
        return True

    raw_cookie = _get_request_cookie_value(AUTH_COOKIE_NAME)
    payload = _deserialize_auth_cookie(raw_cookie)
    if not payload:
        _set_auth_cookie_sync_pending(False)
        if raw_cookie:
            _queue_auth_cookie_clear()
        return False

    access_token = payload.get("access_token")
    refresh_token = payload.get("refresh_token")
    if not refresh_token:
        _queue_auth_cookie_clear()
        return False

    client = get_anon_supabase_client()
    try:
        try:
            auth_result = client.auth.set_session(access_token, refresh_token) if access_token else client.auth.refresh_session(refresh_token)
        except Exception:
            auth_result = client.auth.refresh_session(refresh_token)

        if not auth_result.user or not auth_result.session:
            raise RuntimeError("session_restore_failed")
        if not _is_admin_user(client=client, user_id=auth_result.user.id):
            client.auth.sign_out()
            raise PermissionError("not_admin")

        _set_authenticated_state(
            client=client,
            user=auth_result.user,
            access_token=auth_result.session.access_token,
            refresh_token=auth_result.session.refresh_token,
        )
        ensure_auth_cookie_persistence()
        return True
    except Exception:
        _queue_auth_cookie_clear()
        for key in AUTH_KEYS:
            st.session_state[key] = None if key != "is_authenticated" else False
        _set_auth_cookie_sync_pending(False)
        return False


def logout_user() -> None:
    """Logout current user and clear auth-related session state."""
    client = st.session_state.get("supabase_client_user")
    if client:
        client.auth.sign_out()
    _queue_auth_cookie_clear()
    for key in AUTH_KEYS:
        st.session_state.pop(key, None)
    st.session_state[AUTH_COOKIE_SYNC_PENDING_KEY] = False
    st.switch_page("Home.py")


def get_user_client():
    """Return authenticated user client from session."""
    return st.session_state.get("supabase_client_user")


def require_admin_session() -> None:
    """Guard protected pages and redirect to Home.py when unauthorized."""
    initialize_auth_state()
    if not st.session_state.get("is_authenticated") or not st.session_state.get("current_user"):
        restored = restore_login_from_cookie()
        if restored is None:
            st.info("ログイン状態を復元しています。数秒後に自動で続行します。")
            st.stop()
        if not restored:
            st.switch_page("Home.py")
            st.stop()
    if not st.session_state.get("is_authenticated") or not st.session_state.get("current_user"):
        st.switch_page("Home.py")
        st.stop()
    checked_at = int(st.session_state.get("admin_checked_at") or 0)
    if checked_at and int(time.time()) - checked_at <= 60:
        ensure_auth_cookie_persistence()
        return
    client = get_user_client()
    user_id = st.session_state["current_user"]["id"]
    admin = (
        client.table("app_users")
        .select("user_id")
        .eq("user_id", user_id)
        .eq("role", "admin")
        .maybe_single()
        .execute()
    )
    if not admin.data:
        logout_user()
        st.error("管理者権限がありません。")
        st.stop()
    st.session_state["admin_checked_at"] = int(time.time())
    ensure_auth_cookie_persistence()
