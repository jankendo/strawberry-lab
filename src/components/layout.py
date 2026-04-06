"""Shared layout helpers for consistent UX."""

from __future__ import annotations

from html import escape

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

_SURFACE_TONE_ALIASES = {
    "default": "default",
    "neutral": "default",
    "soft": "soft",
    "muted": "soft",
    "accent": "accent",
    "brand": "accent",
}


def inject_app_style() -> None:
    """Inject shared production-like CSS for Japanese-first UI."""
    st.markdown(
        """
        <style>
        :root {
            --sl-primary: #7a1236;
            --sl-primary-strong: #5f0e2a;
            --sl-accent: #d61f53;
            --sl-surface: #ffffff;
            --sl-surface-soft: #fff7fb;
            --sl-border: #efd5df;
            --sl-border-strong: #e7c2d1;
            --sl-text: #4f3d44;
            --sl-muted: #6a5860;
            --sl-shadow-soft: 0 8px 22px rgba(118, 35, 64, 0.08);
            --sl-shadow-pop: 0 14px 34px rgba(118, 35, 64, 0.14);
        }
        html, body, [class*="css"], [data-testid="stAppViewContainer"] {
            font-family: "Noto Sans JP", "Hiragino Kaku Gothic ProN", "Yu Gothic UI",
                         "Meiryo", "Segoe UI", sans-serif;
        }
        .block-container {
            padding-top: 0.9rem;
            padding-bottom: 2.5rem;
            max-width: 1240px;
        }
        [data-testid="stAppViewContainer"] {
            background:
                radial-gradient(1120px 420px at 0% -120px, #ffe8f1 0%, rgba(255, 255, 255, 0) 64%),
                linear-gradient(180deg, #fff8fb 0%, #ffffff 320px);
        }
        div[data-testid="stToolbar"] {
            right: 0.8rem;
        }
        .sl-page-header,
        .sl-hero-banner {
            position: relative;
            overflow: hidden;
            padding: 1rem 1.1rem;
            margin: 0 0 1rem;
            border: 1px solid var(--sl-border);
            border-radius: 18px;
            background:
                radial-gradient(460px 190px at 96% -70px, rgba(214, 31, 83, 0.2) 0%, rgba(214, 31, 83, 0) 75%),
                linear-gradient(132deg, #fffafe 0%, #fff3f9 52%, #ffffff 100%);
            box-shadow: var(--sl-shadow-soft);
        }
        .sl-page-header::before,
        .sl-hero-banner::before {
            content: "";
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 3px;
            background: linear-gradient(90deg, #d61f53 0%, #f34d81 46%, rgba(243, 77, 129, 0.22) 100%);
        }
        .sl-hero-eyebrow {
            display: inline-flex;
            margin-bottom: 0.45rem;
            padding: 0.16rem 0.6rem;
            border-radius: 999px;
            border: 1px solid #f4c8d9;
            background: rgba(255, 255, 255, 0.95);
            color: #9a3560;
            font-size: 0.76rem;
            font-weight: 600;
            letter-spacing: 0.05em;
        }
        .sl-page-header h1,
        .sl-hero-banner h1 {
            margin: 0 0 0.26rem;
            font-size: 2rem;
            letter-spacing: 0.018em;
            line-height: 1.24;
            color: var(--sl-primary);
        }
        .sl-page-header p,
        .sl-hero-banner p {
            margin: 0;
            color: #5d4d53;
            font-size: 0.95rem;
            line-height: 1.66;
        }
        .sl-hero-meta {
            display: flex;
            flex-wrap: wrap;
            gap: 0.42rem;
            margin-top: 0.62rem;
        }
        .sl-chip {
            display: inline-flex;
            align-items: center;
            min-height: 24px;
            padding: 0.12rem 0.58rem;
            border-radius: 999px;
            border: 1px solid #efcddd;
            background: #fff;
            color: #7b4860;
            font-size: 0.76rem;
            font-weight: 600;
            white-space: nowrap;
        }
        .sl-chip-soft {
            background: #fff6fa;
        }
        .sl-action-bar {
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            justify-content: space-between;
            gap: 0.62rem 0.9rem;
            margin: 0.35rem 0 0.95rem;
            padding: 0.72rem 0.9rem;
            border: 1px solid var(--sl-border);
            border-radius: 14px;
            background: #fff;
            box-shadow: 0 4px 14px rgba(118, 35, 64, 0.05);
        }
        .sl-action-copy {
            min-width: 180px;
        }
        .sl-action-title {
            color: var(--sl-primary);
            font-size: 0.9rem;
            font-weight: 700;
            line-height: 1.35;
        }
        .sl-action-description {
            margin-top: 0.08rem;
            color: var(--sl-muted);
            font-size: 0.8rem;
            line-height: 1.5;
        }
        .sl-action-group {
            display: flex;
            flex-wrap: wrap;
            gap: 0.4rem;
        }
        .sl-action-item {
            display: inline-flex;
            align-items: center;
            min-height: 24px;
            padding: 0.12rem 0.6rem;
            border-radius: 999px;
            border: 1px solid #eec5d6;
            background: #fff7fb;
            color: #7d4b62;
            font-size: 0.76rem;
            font-weight: 600;
            white-space: nowrap;
        }
        .sl-page-lead {
            margin-top: 0.62rem;
            margin-bottom: 1rem;
            color: #5c4850;
            font-size: 0.95rem;
            line-height: 1.6;
            background: #fff;
            border: 1px solid #f0dfe5;
            border-radius: 13px;
            padding: 0.76rem 0.92rem;
            box-shadow: 0 4px 14px rgba(118, 35, 64, 0.04);
        }
        .sl-section-container,
        .sl-surface {
            background: var(--sl-surface);
            border: 1px solid var(--sl-border);
            border-radius: 14px;
            padding: 0.82rem 0.95rem;
            margin-bottom: 0.74rem;
        }
        .sl-surface-soft {
            background: var(--sl-surface-soft);
        }
        .sl-surface-accent {
            background: linear-gradient(132deg, #fff8fc 0%, #fff2f8 100%);
            border-color: var(--sl-border-strong);
        }
        .sl-surface-elevated {
            box-shadow: var(--sl-shadow-soft);
        }
        .sl-surface-title {
            color: var(--sl-primary);
            font-size: 0.93rem;
            font-weight: 700;
            line-height: 1.4;
            margin-bottom: 0.16rem;
        }
        .sl-surface-subtitle {
            color: var(--sl-muted);
            font-size: 0.8rem;
            line-height: 1.5;
            margin-bottom: 0.36rem;
        }
        .sl-surface-content {
            color: var(--sl-text);
            line-height: 1.64;
            word-break: break-word;
        }
        .sl-section-title {
            margin-top: 1rem;
            margin-bottom: 0.36rem;
            font-size: 1.14rem;
            font-weight: 650;
            letter-spacing: 0.01em;
            line-height: 1.35;
            border-left: 4px solid #d61f53;
            padding-left: 0.56rem;
        }
        .sl-muted {
            color: #69575f;
            font-size: 0.88rem;
            line-height: 1.56;
        }
        .sl-badge {
            display: inline-flex;
            align-items: center;
            gap: 0.28rem;
            min-height: 24px;
            padding: 0.14rem 0.58rem;
            border-radius: 999px;
            border: 1px solid transparent;
            font-size: 0.75rem;
            font-weight: 700;
            line-height: 1.2;
            white-space: nowrap;
        }
        .sl-badge-neutral {
            color: #6f5962;
            background: #f8f4f6;
            border-color: #e8dce2;
        }
        .sl-badge-success {
            color: #206043;
            background: #eefaf3;
            border-color: #ccebd9;
        }
        .sl-badge-warning {
            color: #7a4f07;
            background: #fff8eb;
            border-color: #f3dfb8;
        }
        .sl-badge-danger {
            color: #8f2437;
            background: #fff0f3;
            border-color: #f1c8d2;
        }
        .sl-badge-info {
            color: #284f86;
            background: #eff5ff;
            border-color: #d0def9;
        }
        .sl-kpi-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
            gap: 11px;
            margin: 0.38rem 0 0.95rem;
        }
        .sl-kpi-card {
            background: linear-gradient(152deg, #ffffff 0%, #fff8fb 100%);
            border: 1px solid #edd2dd;
            border-radius: 14px;
            padding: 0.78rem 0.92rem;
            box-shadow: 0 8px 20px rgba(118, 35, 64, 0.07);
        }
        .sl-kpi-label {
            font-size: 0.82rem;
            color: #6f5961;
            margin-bottom: 0.24rem;
        }
        .sl-kpi-value {
            font-size: 1.36rem;
            font-weight: 700;
            color: var(--sl-primary);
            line-height: 1.2;
        }
        .sl-kpi-sub {
            margin-top: 0.13rem;
            color: #7a6a70;
            font-size: 0.75rem;
        }
        .sl-info-card {
            background: #ffffff;
            border: 1px solid var(--sl-border);
            border-radius: 14px;
            padding: 0.82rem 0.95rem;
            margin-bottom: 0.72rem;
            box-shadow: 0 8px 20px rgba(118, 35, 64, 0.06);
            line-height: 1.64;
            color: var(--sl-text);
        }
        .sl-info-card strong {
            color: var(--sl-primary);
        }
        @media (max-width: 740px) {
            .sl-page-header h1,
            .sl-hero-banner h1 {
                font-size: 1.54rem;
            }
            .sl-page-header,
            .sl-hero-banner {
                padding: 0.88rem 0.92rem;
            }
            .sl-action-bar {
                padding: 0.64rem 0.76rem;
            }
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


def _build_status_badge_html(label: str, tone: str = "neutral", icon: str | None = None) -> str:
    tone_class = _normalize_badge_tone(tone)
    icon_html = f'<span aria-hidden="true">{escape(icon)}</span>' if icon else ""
    return (
        f'<span class="sl-badge sl-badge-{tone_class}">'
        f"{icon_html}<span>{escape(label)}</span>"
        "</span>"
    )


def render_page_header(title: str, description: str) -> None:
    """Render consistent page title block."""
    st.markdown(
        f"""
        <div class="sl-page-header">
          <h1>{title}</h1>
          <p>{description}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_hero_banner(
    title: str,
    description: str,
    *,
    eyebrow: str | None = None,
    chips: list[str] | None = None,
) -> None:
    """Render modern hero banner with optional context chips."""
    eyebrow_html = f'<div class="sl-hero-eyebrow">{escape(eyebrow)}</div>' if eyebrow else ""
    chips_html = "".join(f'<span class="sl-chip sl-chip-soft">{escape(chip)}</span>' for chip in (chips or []))
    meta_html = f'<div class="sl-hero-meta">{chips_html}</div>' if chips_html else ""
    st.markdown(
        f"""
        <section class="sl-hero-banner">
          {eyebrow_html}
          <h1>{escape(title)}</h1>
          <p>{escape(description)}</p>
          {meta_html}
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_action_bar(
    actions: list[str] | None = None,
    *,
    title: str | None = None,
    description: str | None = None,
) -> None:
    """Render action summary bar with optional action chips."""
    if not title and not description and not actions:
        return
    title_html = f'<div class="sl-action-title">{escape(title)}</div>' if title else ""
    description_html = f'<div class="sl-action-description">{escape(description)}</div>' if description else ""
    copy_html = f'<div class="sl-action-copy">{title_html}{description_html}</div>' if (title_html or description_html) else ""
    actions_html = "".join(f'<span class="sl-action-item">{escape(action)}</span>' for action in (actions or []))
    group_html = f'<div class="sl-action-group">{actions_html}</div>' if actions_html else ""
    st.markdown(
        f"""
        <div class="sl-action-bar">
          {copy_html}
          {group_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_lead(text: str) -> None:
    """Render highlighted lead paragraph."""
    st.markdown(f'<div class="sl-page-lead">{text}</div>', unsafe_allow_html=True)


def render_section_title(title: str, description: str | None = None) -> None:
    """Render section heading and optional supporting text."""
    st.markdown(f'<div class="sl-section-title">{title}</div>', unsafe_allow_html=True)
    if description:
        st.markdown(f'<div class="sl-muted">{description}</div>', unsafe_allow_html=True)


def render_status_badge(label: str, tone: str = "neutral", *, icon: str | None = None) -> str:
    """Render inline status badge and return generated HTML."""
    badge_html = _build_status_badge_html(label=label, tone=tone, icon=icon)
    st.markdown(badge_html, unsafe_allow_html=True)
    return badge_html


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
    elevated_class = " sl-surface-elevated" if elevated else ""
    title_html = f'<div class="sl-surface-title">{escape(title)}</div>' if title else ""
    subtitle_html = f'<div class="sl-surface-subtitle">{escape(subtitle)}</div>' if subtitle else ""
    st.markdown(
        f"""
        <section class="sl-surface sl-section-container sl-surface-{tone_class}{elevated_class}">
          {title_html}
          {subtitle_html}
          <div class="sl-surface-content">{content}</div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_kpi_cards(items: list[tuple[str, str, str | None]]) -> None:
    """Render compact KPI cards."""
    cards_html = []
    for label, value, sub_text in items:
        sub = f'<div class="sl-kpi-sub">{sub_text}</div>' if sub_text else ""
        cards_html.append(
            f"""
            <div class="sl-kpi-card">
              <div class="sl-kpi-label">{label}</div>
              <div class="sl-kpi-value">{value}</div>
              {sub}
            </div>
            """
        )
    st.markdown(f'<div class="sl-kpi-grid">{"".join(cards_html)}</div>', unsafe_allow_html=True)


def render_info_card(text: str) -> None:
    """Render informational card block."""
    st.markdown(f'<div class="sl-info-card sl-surface sl-surface-elevated">{text}</div>', unsafe_allow_html=True)
