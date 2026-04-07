"""Authentication and authorization service."""

from __future__ import annotations

import json
import os
import secrets
import time

import streamlit as st

from src.core.supabase_client import get_anon_supabase_client


AUTH_KEYS = ("current_user", "supabase_client_user", "is_authenticated", "access_token", "refresh_token", "admin_checked_at")
AUTH_COOKIE_NAME = "remember_auth_v1"
AUTH_COOKIE_PREFIX = "strawberrylab_"
AUTH_COOKIE_TTL_DAYS = 30
AUTH_PERSISTENCE_READY = "ready"
AUTH_PERSISTENCE_READY_EPHEMERAL_SECRET = "ready_ephemeral_secret"
AUTH_PERSISTENCE_MISSING_SECRET = "missing_secret"
AUTH_PERSISTENCE_MANAGER_UNAVAILABLE = "cookie_manager_unavailable"
AUTH_PERSISTENCE_MANAGER_NOT_READY = "cookie_manager_not_ready"
AUTH_PERSISTENCE_MANAGER_NOT_READY_EPHEMERAL_SECRET = "cookie_manager_not_ready_ephemeral_secret"

_EPHEMERAL_COOKIE_SECRET: str | None = None
_COOKIE_MANAGER_RUN_CACHE: dict[str, object | None] = {
    "session_id": None,
    "run_context": None,
    "secret": None,
    "is_ephemeral": None,
    "manager": None,
    "status": None,
}


def initialize_auth_state() -> None:
    """Initialize auth session state keys."""
    for key in AUTH_KEYS:
        if key not in st.session_state:
            st.session_state[key] = None if key != "is_authenticated" else False


def _get_script_run_cache_identity() -> tuple[str | None, object | None]:
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx

        context = get_script_run_ctx()
        if context is None:
            return None, None
        page_hash = getattr(context, "page_script_hash", "") or getattr(context, "active_script_hash", "") or "no-page"
        # Streamlit fragments can replace ctx.cursors mid-run, so cache against
        # collections that are recreated only when a new script run starts.
        return f"{context.session_id}:{page_hash}", getattr(context, "widget_ids_this_run", None)
    except Exception:
        return None, None


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


def _get_cookie_manager_with_status():
    secret, is_ephemeral = _get_cookie_secret()
    if not secret:
        return None, AUTH_PERSISTENCE_MISSING_SECRET

    session_id, run_context = _get_script_run_cache_identity()
    if (
        _COOKIE_MANAGER_RUN_CACHE.get("session_id") == session_id
        and _COOKIE_MANAGER_RUN_CACHE.get("run_context") is run_context
        and _COOKIE_MANAGER_RUN_CACHE.get("secret") == secret
        and _COOKIE_MANAGER_RUN_CACHE.get("is_ephemeral") == is_ephemeral
    ):
        return _COOKIE_MANAGER_RUN_CACHE.get("manager"), _COOKIE_MANAGER_RUN_CACHE.get("status")

    try:
        from streamlit_cookies_manager import EncryptedCookieManager
    except Exception:
        _COOKIE_MANAGER_RUN_CACHE.update(
            {
                "session_id": session_id,
                "run_context": run_context,
                "secret": secret,
                "is_ephemeral": is_ephemeral,
                "manager": None,
                "status": AUTH_PERSISTENCE_MANAGER_UNAVAILABLE,
            }
        )
        return None, AUTH_PERSISTENCE_MANAGER_UNAVAILABLE

    cookies = EncryptedCookieManager(prefix=AUTH_COOKIE_PREFIX, password=secret)
    if not cookies.ready():
        status = (
            AUTH_PERSISTENCE_MANAGER_NOT_READY_EPHEMERAL_SECRET
            if is_ephemeral
            else AUTH_PERSISTENCE_MANAGER_NOT_READY
        )
        _COOKIE_MANAGER_RUN_CACHE.update(
            {
                "session_id": session_id,
                "run_context": run_context,
                "secret": secret,
                "is_ephemeral": is_ephemeral,
                "manager": None,
                "status": status,
            }
        )
        return None, status

    status = AUTH_PERSISTENCE_READY_EPHEMERAL_SECRET if is_ephemeral else AUTH_PERSISTENCE_READY
    _COOKIE_MANAGER_RUN_CACHE.update(
        {
            "session_id": session_id,
            "run_context": run_context,
            "secret": secret,
            "is_ephemeral": is_ephemeral,
            "manager": cookies,
            "status": status,
        }
    )
    return cookies, status


def _get_cookie_manager():
    cookies, _ = _get_cookie_manager_with_status()
    return cookies


def _clear_auth_cookie(cookies=None) -> None:
    if cookies is None:
        cookies = _get_cookie_manager()
    if cookies is None:
        return
    if AUTH_COOKIE_NAME in cookies:
        del cookies[AUTH_COOKIE_NAME]
        cookies.save()


def _save_auth_cookie(*, access_token: str, refresh_token: str) -> bool:
    cookies = _get_cookie_manager()
    if cookies is None:
        return False
    payload = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": int(time.time()) + AUTH_COOKIE_TTL_DAYS * 24 * 60 * 60,
    }
    cookies[AUTH_COOKIE_NAME] = json.dumps(payload, ensure_ascii=False)
    cookies.save()
    return True


def _read_auth_cookie() -> dict | None:
    cookies = _get_cookie_manager()
    if cookies is None:
        return None
    raw = cookies.get(AUTH_COOKIE_NAME)
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except Exception:
        _clear_auth_cookie(cookies)
        return None
    expires_at = int(payload.get("expires_at", 0))
    if not expires_at or expires_at <= int(time.time()):
        _clear_auth_cookie(cookies)
        return None
    return payload


def _set_authenticated_state(*, client, user, access_token: str, refresh_token: str) -> None:
    st.session_state["current_user"] = {"id": user.id, "email": user.email}
    st.session_state["supabase_client_user"] = client
    st.session_state["is_authenticated"] = True
    st.session_state["access_token"] = access_token
    st.session_state["refresh_token"] = refresh_token
    st.session_state["admin_checked_at"] = int(time.time())


def get_auth_persistence_status() -> dict[str, str | bool]:
    """Return availability information for encrypted auth-cookie persistence."""
    _, status = _get_cookie_manager_with_status()
    if status == AUTH_PERSISTENCE_READY:
        return {
            "available": True,
            "code": AUTH_PERSISTENCE_READY,
            "message": "30日ログイン保持は有効です。",
        }
    if status == AUTH_PERSISTENCE_READY_EPHEMERAL_SECRET:
        return {
            "available": True,
            "code": AUTH_PERSISTENCE_READY_EPHEMERAL_SECRET,
            "message": "APP_COOKIE_SECRET が未設定のため、一時ランダム秘密鍵でログイン保持を継続中です。再起動/再デプロイ時に保持がリセットされる場合があります。",
        }
    if status == AUTH_PERSISTENCE_MISSING_SECRET:
        return {
            "available": False,
            "code": AUTH_PERSISTENCE_MISSING_SECRET,
            "message": "APP_COOKIE_SECRET が未設定で、一時秘密鍵の生成にも失敗したため、30日ログイン保持は無効です。",
        }
    if status == AUTH_PERSISTENCE_MANAGER_UNAVAILABLE:
        return {
            "available": False,
            "code": AUTH_PERSISTENCE_MANAGER_UNAVAILABLE,
            "message": "クッキー暗号化モジュールを読み込めないため、30日ログイン保持は利用できません。",
        }
    if status == AUTH_PERSISTENCE_MANAGER_NOT_READY_EPHEMERAL_SECRET:
        return {
            "available": False,
            "code": AUTH_PERSISTENCE_MANAGER_NOT_READY_EPHEMERAL_SECRET,
            "message": "ログイン保持クッキーを初期化中です。APP_COOKIE_SECRET 未設定時は一時ランダム秘密鍵を使用するため、再起動/再デプロイ時に保持がリセットされる場合があります。",
        }
    return {
        "available": False,
        "code": AUTH_PERSISTENCE_MANAGER_NOT_READY,
        "message": "ログイン保持クッキーを初期化中です。初回表示後に再試行されます。",
    }


def ensure_auth_cookie_persistence() -> bool:
    """Retry persisting auth cookie when an authenticated session already exists."""
    initialize_auth_state()
    if not st.session_state.get("is_authenticated") or not st.session_state.get("current_user"):
        return False

    access_token = st.session_state.get("access_token")
    refresh_token = st.session_state.get("refresh_token")
    if not access_token or not refresh_token:
        return False

    payload = _read_auth_cookie()
    if payload and payload.get("access_token") == access_token and payload.get("refresh_token") == refresh_token:
        return True
    return _save_auth_cookie(access_token=access_token, refresh_token=refresh_token)


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
    _save_auth_cookie(access_token=result.session.access_token, refresh_token=result.session.refresh_token)


def restore_login_from_cookie() -> bool:
    """Restore login state from encrypted cookie when available."""
    initialize_auth_state()
    if st.session_state.get("is_authenticated") and st.session_state.get("current_user"):
        ensure_auth_cookie_persistence()
        return True
    payload = _read_auth_cookie()
    if not payload:
        return False

    access_token = payload.get("access_token")
    refresh_token = payload.get("refresh_token")
    if not refresh_token:
        _clear_auth_cookie()
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
        _save_auth_cookie(
            access_token=auth_result.session.access_token,
            refresh_token=auth_result.session.refresh_token,
        )
        return True
    except Exception:
        _clear_auth_cookie()
        for key in AUTH_KEYS:
            st.session_state[key] = None if key != "is_authenticated" else False
        return False


def logout_user() -> None:
    """Logout current user and clear auth-related session state."""
    client = st.session_state.get("supabase_client_user")
    if client:
        client.auth.sign_out()
    _clear_auth_cookie()
    for key in AUTH_KEYS:
        st.session_state.pop(key, None)
    st.switch_page("Home.py")


def get_user_client():
    """Return authenticated user client from session."""
    return st.session_state.get("supabase_client_user")


def require_admin_session() -> None:
    """Guard protected pages and redirect to Home.py when unauthorized."""
    initialize_auth_state()
    if not st.session_state.get("is_authenticated") or not st.session_state.get("current_user"):
        if not restore_login_from_cookie():
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
