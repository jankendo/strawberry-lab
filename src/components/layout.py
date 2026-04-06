"""Shared layout helpers for consistent UX."""

from __future__ import annotations

from html import unescape
import os
import re

import streamlit as st

_BADGE_TONE_ALIASES = {
    "default": "neutral",
    "muted": "neutral",
    "ok": "success",
    "positive": "success",
    "warn": "warning",
    "caution": "warning",
    "error": "danger",
    "critical": "danger",
    "primary": "info",
    "accent": "info",
}

_BADGE_TONES = {"neutral", "success", "warning", "danger", "info"}

_BADGE_STYLE = {
    "neutral": {"icon": "◯"},
    "success": {"icon": "✅"},
    "warning": {"icon": "⚠️"},
    "danger": {"icon": "⛔"},
    "info": {"icon": "ℹ️"},
}

_SURFACE_TONE_ALIASES = {
    "default": "default",
    "neutral": "default",
    "soft": "soft",
    "muted": "soft",
    "accent": "accent",
    "brand": "accent",
    "warning": "warning",
    "danger": "danger",
}

_HTML_LINE_BREAK_RE = re.compile(r"(?i)<br\s*/?>")
_HTML_BLOCK_CLOSE_RE = re.compile(r"(?i)</(?:div|p|section|article|li|ul|ol|h[1-6])>")
_HTML_LIST_OPEN_RE = re.compile(r"(?i)<li[^>]*>")
_HTML_STRONG_OPEN_RE = re.compile(r"(?i)<(?:strong|b)>")
_HTML_STRONG_CLOSE_RE = re.compile(r"(?i)</(?:strong|b)>")
_HTML_TAG_RE = re.compile(r"(?is)<[^>]+>")
_NON_WORD_RE = re.compile(r"[^A-Za-z0-9_]+")
_PLACEHOLDER_VALUES = {"unknown", "none", "null", "-"}


def _as_bool(value: object | None, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on", "y"}:
        return True
    if normalized in {"0", "false", "no", "off", "n"}:
        return False
    return default


def _should_hide_host_chrome() -> bool:
    try:
        secret_value = st.secrets.get("APP_HIDE_HOST_CHROME")
    except Exception:
        secret_value = None
    env_value = os.getenv("APP_HIDE_HOST_CHROME")
    if secret_value is not None:
        return _as_bool(secret_value, default=True)
    if env_value is not None:
        return _as_bool(env_value, default=True)
    return True


def inject_app_style() -> None:
    """Inject product-oriented, neutral-first design tokens and component styles."""
    host_chrome_css = ""
    if _should_hide_host_chrome():
        host_chrome_css = """
        header[data-testid="stHeader"],
        [data-testid="stToolbar"],
        [data-testid="stDecoration"],
        [data-testid="stStatusWidget"],
        #MainMenu,
        button[kind="header"] {
            display: none !important;
            visibility: hidden !important;
            height: 0 !important;
        }
        """

    style = """
    <style>
    :root {
        --sl-bg: #f6f8fb;
        --sl-surface: #ffffff;
        --sl-surface-soft: #f3f5f8;
        --sl-surface-muted: #edf1f6;
        --sl-primary: #e8334a;
        --sl-primary-strong: #b92338;
        --sl-text: #1f2937;
        --sl-heading: #111827;
        --sl-muted: #5b6472;
        --sl-border: #d7dde7;
        --sl-border-strong: #bcc6d6;
        --sl-success: #1f8a4c;
        --sl-warning: #b87400;
        --sl-danger: #c23535;
        --sl-info: #2f6feb;
        --sl-space-1: 0.5rem;   /* 8px */
        --sl-space-2: 1rem;     /* 16px */
        --sl-space-3: 1.5rem;   /* 24px */
        --sl-space-4: 2rem;     /* 32px */
        --sl-space-5: 2.5rem;   /* 40px */
        --sl-space-6: 3rem;     /* 48px */
        --sl-touch-target: 44px;
        --sl-touch-target-mobile: 48px;
        --sl-safe-bottom: env(safe-area-inset-bottom, 0px);
        --sl-body-size: 0.95rem;
        --sl-caption-size: 0.84rem;
        --sl-mobile-gap: 0.72rem;
    }

    [data-testid="stAppViewContainer"],
    [data-testid="stSidebar"] {
        font-family: "Yu Gothic UI", "Hiragino Kaku Gothic ProN", "Hiragino Sans", "Noto Sans JP", sans-serif;
    }
    [data-testid="stAppViewContainer"] {
        background: var(--sl-bg);
        color: var(--sl-text);
    }
    .block-container {
        max-width: 1320px;
        padding-top: var(--sl-space-3);
        padding-bottom: var(--sl-space-5);
        padding-left: var(--sl-space-3);
        padding-right: var(--sl-space-3);
    }
    [data-testid="stVerticalBlock"] {
        gap: var(--sl-space-3);
    }

    h1 {
        font-size: 2.35rem;   /* ~38px */
        line-height: 1.25;
        margin-top: var(--sl-space-1);
        margin-bottom: var(--sl-space-2);
    }
    h2 {
        font-size: 1.72rem;   /* ~27px */
        line-height: 1.3;
        margin-bottom: var(--sl-space-2);
    }
    h3 {
        font-size: 1.2rem;    /* ~19px */
        line-height: 1.35;
        margin-bottom: var(--sl-space-1);
    }
    h1, h2, h3, h4, h5, h6 {
        color: var(--sl-heading);
        letter-spacing: 0.01em;
    }
    p, label, [data-testid="stMarkdownContainer"] {
        color: var(--sl-text);
        font-size: var(--sl-body-size);
        line-height: 1.6;
    }
    [data-testid="stCaptionContainer"] {
        color: var(--sl-muted);
        font-size: var(--sl-caption-size);
    }

    div[data-testid="stVerticalBlockBorderWrapper"] {
        background: var(--sl-surface);
        border: 1px solid var(--sl-border);
        border-radius: 12px;
        padding: var(--sl-space-2);
        margin-bottom: var(--sl-space-2);
        box-shadow: 0 2px 12px rgba(17, 24, 39, 0.04);
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:focus-within {
        border-color: var(--sl-primary);
        box-shadow: 0 0 0 2px rgba(232, 51, 74, 0.16);
    }

    div[data-testid="stMetric"] {
        background: var(--sl-surface);
        border: 1px solid var(--sl-border);
        border-radius: 10px;
        padding: var(--sl-space-1) var(--sl-space-2);
    }
    div[data-testid="stMetricLabel"] {
        color: var(--sl-muted);
        font-size: 0.82rem;
    }
    div[data-testid="stMetricValue"] {
        color: var(--sl-heading);
        font-size: 1.4rem;
        font-weight: 700;
    }

    [data-testid="stButton"] > button,
    [data-testid="stDownloadButton"] > button,
    [data-testid="stFormSubmitButton"] > button {
        min-height: var(--sl-touch-target);
        border-radius: 10px;
        border: 1px solid var(--sl-border-strong);
        background: #ffffff;
        color: var(--sl-text);
        font-weight: 600;
        padding: 0 var(--sl-space-2);
        transition: border-color 0.2s ease, background-color 0.2s ease, box-shadow 0.2s ease, color 0.2s ease;
    }
    [data-testid="stButton"] > button:hover,
    [data-testid="stDownloadButton"] > button:hover,
    [data-testid="stFormSubmitButton"] > button:hover {
        border-color: var(--sl-primary);
        background: #fef8f9;
    }
    [data-testid="stButton"] > button:focus-visible,
    [data-testid="stDownloadButton"] > button:focus-visible,
    [data-testid="stFormSubmitButton"] > button:focus-visible {
        outline: 3px solid rgba(232, 51, 74, 0.24);
        outline-offset: 2px;
    }
    [data-testid="stButton"] > button[kind="primary"],
    [data-testid="stFormSubmitButton"] > button[kind="primary"],
    [data-testid="stDownloadButton"] > button[kind="primary"] {
        background: var(--sl-primary);
        border-color: var(--sl-primary);
        color: #ffffff;
    }
    [data-testid="stButton"] > button[kind="primary"]:hover,
    [data-testid="stFormSubmitButton"] > button[kind="primary"]:hover,
    [data-testid="stDownloadButton"] > button[kind="primary"]:hover {
        background: var(--sl-primary-strong);
        border-color: var(--sl-primary-strong);
        color: #ffffff;
    }
    [data-testid="stButton"] > button:disabled,
    [data-testid="stFormSubmitButton"] > button:disabled {
        background: var(--sl-surface-soft);
        color: var(--sl-muted);
        border-color: var(--sl-border);
    }

    a {
        color: var(--sl-info);
        text-decoration-thickness: 1.2px;
        text-underline-offset: 0.12em;
    }
    a[data-testid="stPageLink-NavLink"] {
        display: flex;
        align-items: center;
        justify-content: space-between;
        min-height: var(--sl-touch-target);
        border-radius: 10px;
        border: 1px solid var(--sl-border-strong);
        background: #ffffff;
        color: var(--sl-text);
        font-weight: 600;
        padding: 0 var(--sl-space-2);
        text-decoration: none;
        margin-bottom: var(--sl-space-1);
        transition: border-color 0.2s ease, background-color 0.2s ease;
    }
    a[data-testid="stPageLink-NavLink"]:hover {
        border-color: var(--sl-primary);
        background: #fef8f9;
    }
    a[data-testid="stPageLink-NavLink"]:focus-visible {
        outline: 3px solid rgba(232, 51, 74, 0.24);
        outline-offset: 2px;
    }

    div[data-baseweb="input"] > div,
    div[data-baseweb="select"] > div,
    div[data-baseweb="textarea"] > div {
        border-color: var(--sl-border-strong) !important;
        background: #ffffff !important;
        border-radius: 10px !important;
        min-height: var(--sl-touch-target);
    }
    div[data-baseweb="input"] input,
    div[data-baseweb="textarea"] textarea {
        background: #ffffff !important;
    }
    div[data-baseweb="input"] > div:focus-within,
    div[data-baseweb="select"] > div:focus-within,
    div[data-baseweb="textarea"] > div:focus-within {
        border-color: var(--sl-primary) !important;
        box-shadow: 0 0 0 2px rgba(232, 51, 74, 0.18) !important;
    }
    div[data-baseweb="input"] > div[data-invalid="true"],
    div[data-baseweb="select"] > div[data-invalid="true"],
    div[data-baseweb="textarea"] > div[data-invalid="true"] {
        border-color: var(--sl-danger) !important;
        background: #fff3f3 !important;
        box-shadow: 0 0 0 2px rgba(194, 53, 53, 0.16) !important;
    }

    [data-testid="stSlider"] [data-baseweb="slider"] {
        min-height: var(--sl-touch-target);
        padding: 0.72rem 0.35rem 0.24rem;
    }
    [data-testid="stSlider"] [data-baseweb="slider"] > div > div {
        min-height: 0.5rem !important;
        border-radius: 999px !important;
    }
    [data-testid="stSlider"] [data-baseweb="slider"] > div > div:first-child {
        background: #d0d8e6 !important;
    }
    [data-testid="stSlider"] [data-baseweb="slider"] > div > div > div {
        background: linear-gradient(90deg, var(--sl-primary), var(--sl-primary-strong)) !important;
        border-radius: 999px !important;
    }
    [data-testid="stSlider"] [role="slider"] {
        width: 1.55rem !important;
        height: 1.55rem !important;
        margin-top: -0.48rem !important;
        border: 3px solid #ffffff !important;
        background: var(--sl-primary) !important;
        box-shadow: 0 0 0 2px rgba(185, 35, 56, 0.22), 0 4px 10px rgba(17, 24, 39, 0.2) !important;
    }
    [data-testid="stSlider"] [role="slider"]:focus-visible {
        outline: 3px solid rgba(232, 51, 74, 0.24) !important;
        outline-offset: 2px;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: var(--sl-space-1);
        margin-bottom: var(--sl-space-2);
    }
    .stTabs [data-baseweb="tab"] {
        min-height: var(--sl-touch-target);
        border-radius: 10px;
        border: 1px solid var(--sl-border-strong);
        padding: 0 var(--sl-space-2);
        background: #ffffff;
        color: var(--sl-text);
        font-weight: 600;
    }
    .stTabs [data-baseweb="tab"]:hover {
        border-color: var(--sl-primary);
        background: #fef8f9;
    }
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background: var(--sl-primary);
        border-color: var(--sl-primary);
        color: #ffffff;
    }

    [data-testid="stSidebar"] {
        background: var(--sl-surface-soft);
        border-right: 1px solid var(--sl-border);
    }
    [data-testid="stSidebar"] .sl-sidebar-brand {
        border: 1px solid var(--sl-border);
        border-radius: 12px;
        background: #ffffff;
        padding: var(--sl-space-2);
        margin-bottom: var(--sl-space-2);
    }
    [data-testid="stSidebar"] .sl-sidebar-brand-title {
        color: var(--sl-heading);
        font-size: 1.02rem;
        font-weight: 700;
    }
    [data-testid="stSidebar"] .sl-sidebar-brand-sub {
        color: var(--sl-muted);
        font-size: 0.78rem;
    }
    [data-testid="stSidebar"] .sl-sidebar-active {
        display: flex;
        align-items: center;
        min-height: var(--sl-touch-target);
        border-radius: 10px;
        border: 1px solid var(--sl-primary);
        background: rgba(232, 51, 74, 0.1);
        color: var(--sl-heading);
        font-weight: 700;
        padding: 0 var(--sl-space-2);
        margin-bottom: var(--sl-space-1);
    }
    [data-testid="stSidebar"] .sl-sidebar-user {
        border: 1px solid var(--sl-border);
        border-radius: 12px;
        background: #ffffff;
        padding: var(--sl-space-2);
        margin-top: var(--sl-space-2);
    }
    .sl-bottom-nav-anchor {
        display: none;
    }
    .sl-bottom-nav-anchor + div[data-testid="stHorizontalBlock"] {
        display: none;
    }
    .sl-bottom-nav-tab-active {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 0.16rem;
        width: 100%;
        min-width: 0;
        min-height: 56px;
        border-radius: 12px;
        border: 1px solid var(--sl-primary);
        background: rgba(232, 51, 74, 0.14);
        color: var(--sl-heading);
        font-weight: 700;
        text-align: center;
        line-height: 1.12;
        padding: 0.2rem 0.15rem;
        box-sizing: border-box;
        overflow: hidden;
    }
    .sl-bottom-nav-tab-active .sl-bottom-nav-icon {
        font-size: 1rem;
        line-height: 1;
        flex-shrink: 0;
    }
    .sl-bottom-nav-tab-active .sl-bottom-nav-label {
        display: block;
        width: 100%;
        max-width: 100%;
        font-size: 0.72rem;
        white-space: normal;
        overflow-wrap: anywhere;
        word-break: keep-all;
    }

    .sl-workspace-meta-row {
        margin-bottom: var(--sl-space-2);
    }
    .sl-meta-chip {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 100%;
        min-height: var(--sl-touch-target);
        padding: 0 var(--sl-space-1);
        border: 1px solid var(--sl-border-strong);
        border-radius: 10px;
        background: #ffffff;
        color: var(--sl-text);
        font-size: 0.86rem;
        font-weight: 600;
        white-space: nowrap;
    }
    .sl-context-chip {
        display: inline-block;
        margin: 0 var(--sl-space-1) var(--sl-space-1) 0;
        padding: 0.24rem 0.62rem;
        border-radius: 999px;
        border: 1px solid var(--sl-border);
        background: var(--sl-surface-soft);
        color: var(--sl-muted);
        font-size: 0.84rem;
        font-weight: 600;
    }
    .sl-user-chip {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 100%;
        min-height: var(--sl-touch-target);
        padding: 0 var(--sl-space-1);
        border-radius: 10px;
        border: 1px solid var(--sl-border-strong);
        background: #ffffff;
        color: var(--sl-text);
        font-size: 0.84rem;
        font-weight: 600;
    }

    .sl-status-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.28rem;
        border-radius: 999px;
        border: 1px solid transparent;
        padding: 0.2rem 0.58rem;
        font-size: 0.82rem;
        font-weight: 700;
    }

    @media (max-width: 820px) {
        .block-container {
            max-width: 100%;
            padding-top: var(--sl-space-2);
            padding-right: 0.75rem;
            padding-left: 0.75rem;
            padding-bottom: calc(8rem + var(--sl-safe-bottom));
        }
        [data-testid="stVerticalBlock"] {
            gap: var(--sl-mobile-gap);
        }
        h1 {
            font-size: 1.7rem;
            line-height: 1.3;
        }
        h2 {
            font-size: 1.38rem;
            line-height: 1.33;
        }
        h3 {
            font-size: 1.08rem;
        }
        p, label, [data-testid="stMarkdownContainer"] {
            font-size: 0.98rem;
            line-height: 1.52;
        }
        [data-testid="stCaptionContainer"] {
            font-size: 0.86rem;
        }
        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 12px;
            padding: 0.84rem;
            margin-bottom: var(--sl-mobile-gap);
        }
        [data-testid="stButton"] > button,
        [data-testid="stDownloadButton"] > button,
        [data-testid="stFormSubmitButton"] > button,
        .stTabs [data-baseweb="tab"],
        .sl-meta-chip,
        .sl-user-chip {
            min-height: var(--sl-touch-target-mobile);
            font-size: 0.98rem;
        }
        div[data-baseweb="input"] > div,
        div[data-baseweb="select"] > div,
        div[data-baseweb="textarea"] > div {
            min-height: var(--sl-touch-target-mobile);
        }
        [data-testid="stSlider"] [data-baseweb="slider"] {
            min-height: calc(var(--sl-touch-target-mobile) + 4px);
            padding-top: 0.84rem;
        }
        [data-testid="stSlider"] [role="slider"] {
            width: 1.68rem !important;
            height: 1.68rem !important;
        }
        [data-testid="stMainBlockContainer"] [data-testid="stVerticalBlock"] > div[data-testid="stHorizontalBlock"] {
            flex-direction: column !important;
            gap: var(--sl-mobile-gap) !important;
        }
        [data-testid="stMainBlockContainer"] [data-testid="stVerticalBlock"] > div[data-testid="stHorizontalBlock"] > div {
            min-width: 100% !important;
            max-width: 100% !important;
            width: 100% !important;
            flex: 1 1 100% !important;
        }
        .sl-bottom-nav-anchor {
            display: block;
            height: 0;
            margin: 0;
            padding: 0;
        }
        .sl-bottom-nav-anchor + div[data-testid="stHorizontalBlock"] {
            display: flex !important;
            flex-direction: row !important;
            gap: 0.3rem !important;
            position: fixed;
            left: 0.55rem;
            right: 0.55rem;
            bottom: calc(var(--sl-safe-bottom) + 0.45rem);
            z-index: 45;
            padding: 0.34rem;
            border: 1px solid var(--sl-border);
            border-radius: 16px;
            background: rgba(255, 255, 255, 0.97);
            box-shadow: 0 -8px 24px rgba(17, 24, 39, 0.18);
            backdrop-filter: blur(8px);
        }
        .sl-bottom-nav-anchor + div[data-testid="stHorizontalBlock"] > div {
            min-width: 0 !important;
            max-width: none !important;
            width: 0 !important;
            flex: 1 1 0 !important;
        }
        .sl-bottom-nav-anchor + div[data-testid="stHorizontalBlock"] [data-testid="stButton"] > button {
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 56px !important;
            border-radius: 12px;
            margin-bottom: 0 !important;
            padding: 0.2rem 0.15rem;
            line-height: 1.12;
            font-size: 0.72rem;
            white-space: pre-line;
            overflow-wrap: anywhere;
            word-break: keep-all;
            box-sizing: border-box;
            overflow: hidden;
        }
        .sl-bottom-nav-anchor + div[data-testid="stHorizontalBlock"] [data-testid="stButton"] > button p {
            width: 100%;
            margin: 0;
            line-height: 1.12;
            white-space: pre-line;
            overflow-wrap: anywhere;
            word-break: keep-all;
            text-align: center;
        }
        [data-testid="stSidebar"] {
            display: none !important;
        }
    }
    .sl-status-neutral {
        color: #4b5563;
        background: #f3f4f6;
        border-color: #d1d5db;
    }
    .sl-status-success {
        color: #166534;
        background: #ecfdf3;
        border-color: #86efac;
    }
    .sl-status-warning {
        color: #92400e;
        background: #fffbeb;
        border-color: #fcd34d;
    }
    .sl-status-danger {
        color: #991b1b;
        background: #fef2f2;
        border-color: #fca5a5;
    }
    .sl-status-info {
        color: #1d4ed8;
        background: #eff6ff;
        border-color: #93c5fd;
    }

    [data-testid="stDataFrame"] thead tr th {
        background: var(--sl-surface-muted) !important;
        color: var(--sl-heading) !important;
    }
    [data-testid="stDataFrame"] tbody tr:hover td {
        background: #f8fbff !important;
    }

    __HOST_CHROME_CSS__
    </style>
    """
    st.markdown(style.replace("__HOST_CHROME_CSS__", host_chrome_css), unsafe_allow_html=True)


def _normalize_badge_tone(tone: str | None) -> str:
    normalized = (tone or "neutral").strip().lower()
    normalized = _BADGE_TONE_ALIASES.get(normalized, normalized)
    return normalized if normalized in _BADGE_TONES else "neutral"


def _normalize_surface_tone(tone: str | None) -> str:
    normalized = (tone or "default").strip().lower()
    return _SURFACE_TONE_ALIASES.get(normalized, "default")


def _collapse_lines(text: str) -> str:
    rows: list[str] = []
    last_was_blank = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            rows.append(stripped)
            last_was_blank = False
            continue
        if not last_was_blank:
            rows.append("")
            last_was_blank = True
    return "\n".join(rows).strip()


def _prepare_html_like_text(value: object | None) -> str:
    text = str(value or "").replace("\r\n", "\n")
    text = _HTML_LINE_BREAK_RE.sub("\n", text)
    text = _HTML_BLOCK_CLOSE_RE.sub("\n", text)
    text = _HTML_LIST_OPEN_RE.sub("- ", text)
    return text


def _sanitize_text(value: object | None) -> str:
    text = _prepare_html_like_text(value)
    text = _HTML_TAG_RE.sub("", text)
    return _collapse_lines(unescape(text))


def _sanitize_markdown(value: object | None) -> str:
    text = _prepare_html_like_text(value)
    text = _HTML_STRONG_OPEN_RE.sub("**", text)
    text = _HTML_STRONG_CLOSE_RE.sub("**", text)
    text = _HTML_TAG_RE.sub("", text)
    return _collapse_lines(unescape(text))


def _keyify(value: object | None) -> str:
    raw = _sanitize_text(value).strip() or "default"
    return _NON_WORD_RE.sub("_", raw).strip("_").lower() or "default"


def _render_workspace_meta_controls(context: str) -> None:
    if not st.session_state.get("is_authenticated"):
        return

    user_email = _sanitize_text((st.session_state.get("current_user") or {}).get("email"))
    if user_email.strip().lower() in _PLACEHOLDER_VALUES:
        user_email = ""
    user_label = user_email or "アカウント"
    notification_count = int(st.session_state.get("ui_notification_count", 0) or 0)
    control_key = _keyify(context)

    left_space, controls_col = st.columns([1.5, 1.9], gap="small")
    with left_space:
        st.caption("研究ワークスペース")
    with controls_col:
        st.markdown('<div class="sl-workspace-meta-row"></div>', unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns([1, 1, 1, 2], gap="small")
        with c1:
            st.markdown(
                f'<span class="sl-meta-chip">🔔 通知 {notification_count}</span>',
                unsafe_allow_html=True,
            )
        with c2:
            st.markdown('<span class="sl-meta-chip">❓ ヘルプ</span>', unsafe_allow_html=True)
        with c3:
            if st.button("⚙️ 設定", key=f"workspace_settings_{control_key}", type="secondary", use_container_width=True):
                st.switch_page("pages/07_settings.py")
        with c4:
            st.markdown(
                f'<span class="sl-user-chip">👤 {user_label}</span>',
                unsafe_allow_html=True,
            )


def render_page_header(title: str, description: str) -> None:
    """Render consistent page title block."""
    with st.container(border=True):
        st.markdown(f"## {_sanitize_text(title)}")
        st.write(_sanitize_text(description))


def render_hero_banner(
    title: str,
    description: str,
    *,
    eyebrow: str | None = None,
    chips: list[str] | None = None,
) -> None:
    """Render top hero block with workspace controls."""
    with st.container(border=True):
        _render_workspace_meta_controls(title)
        if eyebrow:
            st.caption(_sanitize_text(eyebrow))
        st.markdown(f"# {_sanitize_text(title)}")
        st.write(_sanitize_text(description))
        clean_chips = [chip for chip in (_sanitize_text(item) for item in (chips or [])) if chip]
        if clean_chips:
            st.markdown(
                "".join(f'<span class="sl-context-chip">{chip}</span>' for chip in clean_chips),
                unsafe_allow_html=True,
            )


def render_action_bar(
    actions: list[str] | None = None,
    *,
    title: str | None = None,
    description: str | None = None,
) -> None:
    """Render compact action summary with low visual dominance."""
    clean_title = _sanitize_text(title)
    clean_description = _sanitize_text(description)
    clean_actions = [action for action in (_sanitize_text(item) for item in (actions or [])) if action]
    if not clean_title and not clean_description and not clean_actions:
        return

    with st.container(border=True):
        if clean_title:
            st.markdown(f"**{clean_title}**")
        if clean_description:
            st.caption(clean_description)
        if clean_actions:
            st.markdown(
                "".join(f'<span class="sl-context-chip">{action}</span>' for action in clean_actions),
                unsafe_allow_html=True,
            )


def render_sticky_primary_action_anchor(anchor_id: str) -> None:
    """Mark the next primary action so it can dock near the viewport bottom on mobile."""
    marker = _keyify(anchor_id)
    st.markdown(
        f'<div class="sl-sticky-primary-anchor" data-sl-sticky-anchor="{marker}" aria-hidden="true"></div>',
        unsafe_allow_html=True,
    )


def render_lead(text: str) -> None:
    """Render highlighted lead paragraph."""
    with st.container(border=True):
        st.write(_sanitize_markdown(text))


def render_section_title(title: str, description: str | None = None) -> None:
    """Render section heading and optional supporting text."""
    st.markdown(f"### {_sanitize_text(title)}")
    if description:
        st.caption(_sanitize_text(description))


def render_status_badge(label: str, tone: str = "neutral", *, icon: str | None = None) -> str:
    """Render status badge text and return rendered value."""
    tone_key = _normalize_badge_tone(tone)
    style = _BADGE_STYLE[tone_key]
    icon_text = _sanitize_text(icon) if icon else style["icon"]
    label_text = _sanitize_text(label)
    badge_text = f"{icon_text} {label_text}".strip()
    st.markdown(
        f'<span class="sl-status-badge sl-status-{tone_key}">{badge_text}</span>',
        unsafe_allow_html=True,
    )
    return badge_text


def render_surface(
    content: str,
    *,
    title: str | None = None,
    subtitle: str | None = None,
    tone: str = "default",
    elevated: bool = False,
) -> None:
    """Render reusable section/card surface."""
    tone_class = _normalize_surface_tone(tone)
    clean_title = _sanitize_text(title)
    clean_subtitle = _sanitize_text(subtitle)
    clean_content = _sanitize_markdown(content)

    _ = elevated  # kept for backward compatibility
    with st.container(border=True):
        if tone_class in {"accent", "warning", "danger"}:
            label_map = {"accent": "重要", "warning": "注意", "danger": "警告"}
            tone_map = {"accent": "info", "warning": "warning", "danger": "danger"}
            render_status_badge(label_map[tone_class], tone=tone_map[tone_class])
        if clean_title:
            st.markdown(f"**{clean_title}**")
        if clean_subtitle:
            st.caption(clean_subtitle)
        if clean_content:
            st.markdown(clean_content)


def render_kpi_cards(items: list[tuple[str, str, str | None]]) -> None:
    """Render compact KPI cards in wrapped rows."""
    if not items:
        return

    per_row = 4
    for start in range(0, len(items), per_row):
        row_items = items[start : start + per_row]
        columns = st.columns(len(row_items))
        for column, (label, value, sub_text) in zip(columns, row_items, strict=True):
            with column:
                with st.container(border=True):
                    st.metric(_sanitize_text(label), _sanitize_text(value))
                    if sub_text:
                        st.caption(_sanitize_text(sub_text))


def render_info_card(text: str) -> None:
    """Render informational card block."""
    render_surface(text, tone="soft")


def render_empty_state(
    message: str,
    *,
    title: str = "表示できるデータがありません",
    hint: str | None = None,
    action_label: str | None = None,
    action_path: str | None = None,
) -> None:
    """Render empty state with optional next action."""
    sections = [_sanitize_markdown(message)]
    if hint:
        sections.append(_sanitize_markdown(hint))
    render_surface("\n\n".join(part for part in sections if part), title=title, tone="soft")
    if action_label and action_path:
        st.page_link(action_path, label=_sanitize_text(action_label), use_container_width=True)
