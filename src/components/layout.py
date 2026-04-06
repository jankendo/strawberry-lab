"""Shared layout helpers for consistent UX."""

from __future__ import annotations

from html import unescape
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
    "neutral": {"color": "gray", "icon": "◯"},
    "success": {"color": "green", "icon": "✅"},
    "warning": {"color": "orange", "icon": "⚠️"},
    "danger": {"color": "red", "icon": "⛔"},
    "info": {"color": "blue", "icon": "ℹ️"},
}

_SURFACE_TONE_ALIASES = {
    "default": "default",
    "neutral": "default",
    "soft": "soft",
    "muted": "soft",
    "accent": "accent",
    "brand": "accent",
}

_SURFACE_LABELS = {
    "soft": ":blue[補足]",
    "accent": ":red[注目]",
}

_HTML_LINE_BREAK_RE = re.compile(r"(?i)<br\s*/?>")
_HTML_BLOCK_CLOSE_RE = re.compile(r"(?i)</(?:div|p|section|article|li|ul|ol|h[1-6])>")
_HTML_LIST_OPEN_RE = re.compile(r"(?i)<li[^>]*>")
_HTML_STRONG_OPEN_RE = re.compile(r"(?i)<(?:strong|b)>")
_HTML_STRONG_CLOSE_RE = re.compile(r"(?i)</(?:strong|b)>")
_HTML_TAG_RE = re.compile(r"(?is)<[^>]+>")


def inject_app_style() -> None:
    """Inject a high-contrast, strawberry-accent visual system."""
    st.markdown(
        """
        <style>
        :root {
            --sl-bg: #ffffff;
            --sl-surface: #ffffff;
            --sl-surface-soft: #fff7fb;
            --sl-accent: #c42656;
            --sl-accent-strong: #6b0f2f;
            --sl-border: #e8d5df;
            --sl-border-strong: #c992ab;
            --sl-text: #1f2430;
            --sl-heading: #3f1023;
            --sl-muted: #4f4954;
            --sl-space-1: 0.5rem;
            --sl-space-2: 1rem;
            --sl-space-3: 1.5rem;
            --sl-space-4: 2rem;
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
            max-width: 1240px;
            padding-top: var(--sl-space-3);
            padding-bottom: var(--sl-space-4);
            padding-left: var(--sl-space-3);
            padding-right: var(--sl-space-3);
        }
        [data-testid="stVerticalBlock"] {
            gap: var(--sl-space-2);
        }
        h1, h2, h3, h4, h5, h6 {
            color: var(--sl-heading);
            line-height: 1.35;
            letter-spacing: 0.01em;
            margin-bottom: var(--sl-space-1);
        }
        p, label, [data-testid="stMarkdownContainer"] {
            color: var(--sl-text);
            line-height: 1.65;
        }
        [data-testid="stCaptionContainer"] {
            color: var(--sl-muted);
        }
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background: var(--sl-surface);
            border: 1px solid var(--sl-border);
            border-radius: 14px;
            padding: var(--sl-space-2);
            margin-bottom: var(--sl-space-2);
            box-shadow: 0 4px 18px rgba(122, 18, 54, 0.06);
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:focus-within {
            border-color: var(--sl-accent);
            box-shadow: 0 0 0 2px rgba(196, 38, 86, 0.15);
        }
        div[data-testid="stMetric"] {
            background: var(--sl-surface);
            border: 1px solid var(--sl-border);
            border-radius: 12px;
            padding: var(--sl-space-1) var(--sl-space-2);
        }
        div[data-testid="stMetricLabel"] {
            color: var(--sl-muted);
            font-size: 0.84rem;
        }
        div[data-testid="stMetricValue"] {
            color: var(--sl-heading);
            font-size: 1.5rem;
            font-weight: 700;
        }
        [data-testid="stButton"] > button,
        [data-testid="stDownloadButton"] > button,
        [data-testid="stFormSubmitButton"] > button {
            min-height: 40px;
            border-radius: 10px;
            border: 1px solid var(--sl-border-strong);
            background: #ffffff;
            color: var(--sl-accent-strong);
            font-weight: 600;
            padding: 0 var(--sl-space-2);
            transition: border-color 0.2s ease, background-color 0.2s ease, box-shadow 0.2s ease;
        }
        [data-testid="stButton"] > button:hover,
        [data-testid="stDownloadButton"] > button:hover,
        [data-testid="stFormSubmitButton"] > button:hover {
            border-color: var(--sl-accent);
            background: var(--sl-surface-soft);
            color: var(--sl-accent-strong);
        }
        [data-testid="stButton"] > button:focus-visible,
        [data-testid="stDownloadButton"] > button:focus-visible,
        [data-testid="stFormSubmitButton"] > button:focus-visible {
            outline: 3px solid rgba(196, 38, 86, 0.25);
            outline-offset: 2px;
        }
        [data-testid="stButton"] > button[kind="primary"],
        [data-testid="stFormSubmitButton"] > button[kind="primary"] {
            background: var(--sl-accent);
            border-color: var(--sl-accent);
            color: #ffffff;
        }
        [data-testid="stButton"] > button[kind="primary"]:hover,
        [data-testid="stFormSubmitButton"] > button[kind="primary"]:hover {
            background: var(--sl-accent-strong);
            border-color: var(--sl-accent-strong);
            color: #ffffff;
        }
        a {
            color: var(--sl-accent-strong);
            text-decoration-thickness: 1.5px;
            text-underline-offset: 0.16em;
        }
        a[data-testid="stPageLink-NavLink"] {
            display: flex;
            align-items: center;
            justify-content: space-between;
            min-height: 40px;
            border-radius: 10px;
            border: 1px solid var(--sl-border-strong);
            background: #ffffff;
            color: var(--sl-accent-strong);
            font-weight: 600;
            padding: 0 var(--sl-space-2);
            text-decoration: none;
            margin-bottom: var(--sl-space-1);
            transition: border-color 0.2s ease, background-color 0.2s ease;
        }
        a[data-testid="stPageLink-NavLink"]:hover {
            border-color: var(--sl-accent);
            background: var(--sl-surface-soft);
            color: var(--sl-accent-strong);
        }
        a[data-testid="stPageLink-NavLink"]:focus-visible {
            outline: 3px solid rgba(196, 38, 86, 0.25);
            outline-offset: 2px;
        }
        div[data-baseweb="input"] > div,
        div[data-baseweb="select"] > div,
        div[data-baseweb="textarea"] > div {
            border-color: var(--sl-border-strong);
            border-radius: 10px;
            min-height: 40px;
        }
        div[data-baseweb="input"] > div:focus-within,
        div[data-baseweb="select"] > div:focus-within,
        div[data-baseweb="textarea"] > div:focus-within {
            border-color: var(--sl-accent);
            box-shadow: 0 0 0 2px rgba(196, 38, 86, 0.15);
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: var(--sl-space-1);
            margin-bottom: var(--sl-space-2);
        }
        .stTabs [data-baseweb="tab"] {
            min-height: 40px;
            border-radius: 10px;
            border: 1px solid var(--sl-border-strong);
            padding: 0 var(--sl-space-2);
            background: #ffffff;
            color: var(--sl-accent-strong);
            font-weight: 600;
        }
        .stTabs [data-baseweb="tab"]:hover {
            border-color: var(--sl-accent);
            background: var(--sl-surface-soft);
        }
        .stTabs [data-baseweb="tab"][aria-selected="true"] {
            background: var(--sl-accent);
            border-color: var(--sl-accent);
            color: #ffffff;
        }
        [data-testid="stSidebar"] {
            background: var(--sl-surface-soft);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


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
    """Render modern hero banner with optional context chips."""
    with st.container(border=True):
        if eyebrow:
            st.caption(_sanitize_text(eyebrow))
        st.markdown(f"## {_sanitize_text(title)}")
        st.write(_sanitize_text(description))
        clean_chips = [chip for chip in (_sanitize_text(item) for item in (chips or [])) if chip]
        if clean_chips:
            st.markdown(" ".join(f"`{chip}`" for chip in clean_chips))


def render_action_bar(
    actions: list[str] | None = None,
    *,
    title: str | None = None,
    description: str | None = None,
) -> None:
    """Render action summary bar with optional action chips."""
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
            st.markdown(" ".join(f"`{action}`" for action in clean_actions))


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
    st.markdown(f":{style['color']}[**{badge_text}**]")
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

    def _render_body() -> None:
        tone_label = _SURFACE_LABELS.get(tone_class)
        if tone_label:
            st.markdown(tone_label)
        if clean_title:
            title_color = "red" if tone_class == "accent" else "gray"
            st.markdown(f":{title_color}[**{clean_title}**]")
        if clean_subtitle:
            st.caption(clean_subtitle)
        if clean_content:
            st.markdown(clean_content)

    if elevated:
        with st.container(border=True):
            with st.container(border=True):
                _render_body()
        return

    with st.container(border=True):
        _render_body()


def render_kpi_cards(items: list[tuple[str, str, str | None]]) -> None:
    """Render compact KPI cards."""
    if not items:
        return

    columns = st.columns(len(items))
    for column, (label, value, sub_text) in zip(columns, items, strict=True):
        with column:
            with st.container(border=True):
                st.metric(_sanitize_text(label), _sanitize_text(value))
                if sub_text:
                    st.caption(_sanitize_text(sub_text))


def render_info_card(text: str) -> None:
    """Render informational card block."""
    render_surface(text, tone="soft", elevated=True)


def render_empty_state(
    message: str,
    *,
    title: str = "表示できるデータがありません",
    hint: str | None = None,
) -> None:
    """Render neutral empty-state card."""
    sections = [_sanitize_markdown(message)]
    if hint:
        sections.append(_sanitize_markdown(hint))
    render_surface("\n\n".join(part for part in sections if part), title=title, tone="soft", elevated=True)
