"""Shared cache helpers with optional Redis-backed revision keys."""

from __future__ import annotations

import os
from collections.abc import Sequence
from functools import wraps
from threading import Lock
from typing import Any

import streamlit as st

_LOCAL_REVISIONS: dict[str, int] = {}
_LOCAL_REVISIONS_LOCK = Lock()


def _read_setting(key: str, default: str | None = None) -> str | None:
    try:
        if hasattr(st, "secrets"):
            secret_value = st.secrets.get(key)
            if secret_value not in {None, ""}:
                return str(secret_value)
    except Exception:
        pass
    env_value = os.getenv(key)
    if env_value not in {None, ""}:
        return env_value
    return default


def _as_bool(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _cache_namespace() -> str:
    return str(_read_setting("CACHE_NAMESPACE", "ichigodb") or "ichigodb")


@st.cache_resource(show_spinner=False)
def _build_redis_client(redis_url: str):
    import redis

    return redis.Redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=1, socket_timeout=1)


def _get_redis_client(redis_url: str):
    if not redis_url:
        return None
    try:
        client = _build_redis_client(redis_url)
    except Exception:
        return None
    try:
        client.ping()
        return client
    except Exception:
        try:
            _build_redis_client.clear()
        except Exception:
            pass
        return None


def _revision_key(scope: str) -> str:
    return f"{_cache_namespace()}:cache-revision:{scope.strip().lower()}"


def _get_local_revision(scope: str) -> int:
    key = scope.strip().lower()
    with _LOCAL_REVISIONS_LOCK:
        return int(_LOCAL_REVISIONS.get(key, 0))


def _bump_local_revision(scope: str) -> int:
    key = scope.strip().lower()
    with _LOCAL_REVISIONS_LOCK:
        next_value = int(_LOCAL_REVISIONS.get(key, 0)) + 1
        _LOCAL_REVISIONS[key] = next_value
        return next_value


def _normalize_scopes(scopes: str | Sequence[str]) -> tuple[str, ...]:
    if isinstance(scopes, str):
        values = [scopes]
    else:
        values = list(scopes)
    normalized = [str(scope).strip().lower() for scope in values if str(scope).strip()]
    if not normalized:
        return ("global",)
    return tuple(dict.fromkeys(normalized))


def get_cache_user_scope() -> str:
    """Return a deterministic scope token for cache partitioning."""
    try:
        current_user = st.session_state.get("current_user")
    except Exception:
        return "anonymous"
    if isinstance(current_user, dict):
        user_id = current_user.get("id")
        if user_id:
            return f"user:{user_id}"
    return "anonymous"


def get_cache_revisions(scopes: str | Sequence[str]) -> tuple[str, ...]:
    """Read revision tokens for one or more cache scopes."""
    normalized_scopes = _normalize_scopes(scopes)
    redis_url = str(_read_setting("CACHE_REDIS_URL", "") or "")
    client = _get_redis_client(redis_url)
    revisions: list[str] = []
    for scope in normalized_scopes:
        key = _revision_key(scope)
        revision = None
        if client is not None:
            try:
                revision = client.get(key)
            except Exception:
                revision = None
        if revision is None:
            revision = str(_get_local_revision(scope))
        revisions.append(str(revision))
    return tuple(revisions)


def bump_cache_scopes(*scopes: str) -> None:
    """Increment revision tokens for one or more cache scopes."""
    normalized_scopes = _normalize_scopes(scopes)
    redis_url = str(_read_setting("CACHE_REDIS_URL", "") or "")
    client = _get_redis_client(redis_url)
    for scope in normalized_scopes:
        key = _revision_key(scope)
        bumped = False
        if client is not None:
            try:
                client.incr(key)
                bumped = True
            except Exception:
                bumped = False
        if not bumped:
            _bump_local_revision(scope)


def get_cache_runtime_status() -> dict[str, Any]:
    """Return runtime diagnostics for cache backend assumptions."""
    redis_url = str(_read_setting("CACHE_REDIS_URL", "") or "")
    client = _get_redis_client(redis_url)
    sticky_expected = _as_bool(_read_setting("APP_EXPECT_STICKY_SESSIONS", "true"), default=True)
    redis_enabled = bool(redis_url) and client is not None
    mode = "redis" if redis_enabled else "local"
    if redis_enabled:
        summary = "Redis共有キャッシュ無効化を使用中です。"
    elif sticky_expected:
        summary = "Redis未使用のため、同一ユーザーを同一インスタンスへ固定する運用を推奨します。"
    else:
        summary = "Redis未使用のローカルキャッシュで動作中です。"
    return {
        "mode": mode,
        "redis_configured": bool(redis_url),
        "redis_active": redis_enabled,
        "sticky_sessions_expected": sticky_expected,
        "summary": summary,
    }


def scoped_cache_data(
    *,
    ttl: int,
    scopes: str | Sequence[str],
    use_user_scope: bool = True,
):
    """Wrap ``st.cache_data`` with user scope + revision tokens."""
    normalized_scopes = _normalize_scopes(scopes)

    def decorator(func):
        @st.cache_data(ttl=ttl)
        def _cached(*args, _cache_user_scope: str, _cache_revisions: tuple[str, ...], **kwargs):
            _ = (_cache_user_scope, _cache_revisions)
            return func(*args, **kwargs)

        @wraps(func)
        def _wrapped(*args, **kwargs):
            cache_user_scope = get_cache_user_scope() if use_user_scope else "shared"
            cache_revisions = get_cache_revisions(normalized_scopes)
            return _cached(*args, _cache_user_scope=cache_user_scope, _cache_revisions=cache_revisions, **kwargs)

        _wrapped.clear = _cached.clear
        return _wrapped

    return decorator

