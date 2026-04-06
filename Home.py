"""StrawberryLab home page."""

from __future__ import annotations

import streamlit as st

from src.components.layout import inject_app_style, render_page_header, render_section_title
from src.components.sidebar import render_sidebar
from src.services.auth_service import (
    ensure_auth_cookie_persistence,
    get_auth_persistence_status,
    get_user_client,
    initialize_auth_state,
    login_user,
    restore_login_from_cookie,
)

try:
    from src.components.layout import (
        render_action_bar,
        render_hero_banner,
        render_info_card,
        render_kpi_cards,
        render_lead,
        render_status_badge,
        render_surface,
    )
except ImportError:
    def render_hero_banner(
        title: str,
        description: str,
        *,
        eyebrow: str | None = None,
        chips: list[str] | None = None,
    ) -> None:
        """Fallback hero renderer for partially refreshed runtimes."""
        render_page_header(title, description)
        if eyebrow:
            st.caption(eyebrow)
        if chips:
            st.caption(" / ".join(chips))


    def render_action_bar(
        actions: list[str] | None = None,
        *,
        title: str | None = None,
        description: str | None = None,
    ) -> None:
        """Fallback action bar renderer for partially refreshed runtimes."""
        if title:
            st.write(f"**{title}**")
        if description:
            st.caption(description)
        if actions:
            st.caption(" / ".join(actions))


    def render_lead(text: str) -> None:
        """Fallback lead renderer for partially refreshed runtimes."""
        st.caption(text)


    def render_info_card(text: str) -> None:
        """Fallback info card renderer for partially refreshed runtimes."""
        plain = text.replace("<strong>", "").replace("</strong>", "").replace("<br>", " ")
        st.info(plain)


    def render_kpi_cards(items: list[tuple[str, str, str | None]]) -> None:
        """Fallback KPI renderer for partially refreshed runtimes."""
        columns = st.columns(len(items))
        for column, (label, value, sub_text) in zip(columns, items, strict=True):
            column.metric(label, value, help=sub_text)


    def render_surface(
        content: str,
        *,
        title: str | None = None,
        subtitle: str | None = None,
        tone: str = "default",
        elevated: bool = False,
    ) -> None:
        """Fallback surface renderer for partially refreshed runtimes."""
        if title:
            st.write(f"**{title}**")
        if subtitle:
            st.caption(subtitle)
        plain = content.replace("<strong>", "").replace("</strong>", "").replace("<br>", " ")
        st.write(plain)


    def render_status_badge(label: str, tone: str = "neutral", *, icon: str | None = None) -> str:
        """Fallback status badge renderer for partially refreshed runtimes."""
        _ = tone
        badge_text = f"{icon} {label}" if icon else label
        st.caption(badge_text)
        return badge_text


st.set_page_config(page_title="StrawberryLab", layout="wide")
initialize_auth_state()
restore_login_from_cookie()
ensure_auth_cookie_persistence()
inject_app_style()


@st.cache_data(ttl=120)
def _load_dashboard_metrics() -> dict:
    client = get_user_client()
    if client is None:
        return {
            "active_varieties": 0,
            "active_reviews": 0,
            "notes_count": 0,
            "avg_score": 0.0,
            "latest_status": "-",
            "latest_upserted": 0,
        }

    active_varieties = (
        client.table("varieties").select("id", count="exact", head=True).is_("deleted_at", "null").execute().count or 0
    )
    active_reviews = (
        client.table("reviews").select("id", count="exact", head=True).is_("deleted_at", "null").execute().count or 0
    )
    notes_count = client.table("notes").select("id", count="exact", head=True).is_("deleted_at", "null").execute().count or 0
    overall_rows = client.table("reviews").select("overall").is_("deleted_at", "null").execute().data or []
    avg_score = round(sum(row["overall"] for row in overall_rows) / len(overall_rows), 2) if overall_rows else 0
    latest_scrape = (
        client.table("variety_scrape_runs")
        .select("status,upserted_count")
        .order("started_at", desc=True)
        .limit(1)
        .execute()
        .data
        or []
    )
    return {
        "active_varieties": int(active_varieties),
        "active_reviews": int(active_reviews),
        "notes_count": int(notes_count),
        "avg_score": float(avg_score),
        "latest_status": latest_scrape[0]["status"] if latest_scrape else "-",
        "latest_upserted": int(latest_scrape[0]["upserted_count"]) if latest_scrape else 0,
    }


@st.cache_data(ttl=120)
def _load_latest_reviews() -> list[dict]:
    client = get_user_client()
    if client is None:
        return []
    return (
        client.table("reviews")
        .select("tasted_date,overall,varieties(name)")
        .is_("deleted_at", "null")
        .order("tasted_date", desc=True)
        .limit(5)
        .execute()
        .data
        or []
    )


@st.cache_data(ttl=120)
def _load_recent_scrape_runs() -> list[dict]:
    client = get_user_client()
    if client is None:
        return []
    return (
        client.table("variety_scrape_runs")
        .select("started_at,finished_at,status,upserted_count,failed_count")
        .order("started_at", desc=True)
        .limit(5)
        .execute()
        .data
        or []
    )


def _status_badge_theme(status: str) -> tuple[str, str]:
    normalized = (status or "").strip().lower()
    if normalized in {"success", "succeeded", "completed", "done"}:
        return "success", "✅"
    if normalized in {"running", "in_progress", "queued", "pending"}:
        return "info", "⏳"
    if normalized in {"partial", "warning"}:
        return "warning", "⚠"
    if normalized in {"failed", "error", "cancelled", "canceled"}:
        return "danger", "❗"
    return "neutral", "ℹ"


def _format_latest_reviews(rows: list[dict]) -> list[dict]:
    formatted: list[dict] = []
    for row in rows:
        variety = row.get("varieties") or {}
        formatted.append(
            {
                "試食日": row.get("tasted_date") or "-",
                "品種名": variety.get("name") or "-",
                "総合評価": row.get("overall") if row.get("overall") is not None else "-",
            }
        )
    return formatted


def _format_recent_scrape_runs(rows: list[dict]) -> list[dict]:
    return [
        {
            "開始日時": row.get("started_at") or "-",
            "終了日時": row.get("finished_at") or "-",
            "状態": row.get("status") or "-",
            "更新件数": row.get("upserted_count") or 0,
            "失敗件数": row.get("failed_count") or 0,
        }
        for row in rows
    ]


def _render_login() -> None:
    persistence = get_auth_persistence_status()
    render_hero_banner(
        "StrawberryLab",
        "いちご品種の研究・評価を一元管理するための管理アプリです。",
        eyebrow="管理者ワークスペース",
        chips=["ログインが必要です", "30日ログイン保持対応"],
    )
    render_lead("品種登録情報・試食評価・分析・メモを一体運用する管理者向けワークスペースです。")
    render_action_bar(
        title="サインイン",
        description="登録済み管理者アカウントでログインしてください。",
        actions=["メールアドレス", "パスワード", "ログイン"],
    )
    if persistence["code"] == "ready_ephemeral_secret":
        st.warning(
            f"⚠️ {persistence['message']} 恒久運用では `.streamlit/secrets.toml` に APP_COOKIE_SECRET を設定してください。"
        )
    elif persistence["available"]:
        st.caption("✅ 30日ログイン保持: 有効")
    elif persistence["code"] in {"missing_secret", "cookie_manager_not_ready_ephemeral_secret"}:
        st.warning(f"⚠️ {persistence['message']} `.streamlit/secrets.toml` を確認してください。")
    else:
        st.caption(f"ℹ️ {persistence['message']}")

    _, center, _ = st.columns([1, 1.4, 1])
    with center:
        render_surface(
            "アクセス権限を持つアカウントのみ利用できます。ログイン成功後はダッシュボードへ移動します。",
            title="ログイン",
            subtitle="管理者認証",
            tone="soft",
            elevated=True,
        )
        with st.form("login_form"):
            email = st.text_input("メールアドレス")
            password = st.text_input("パスワード", type="password")
            submitted = st.form_submit_button("ログイン", use_container_width=True)
        if submitted:
            try:
                login_user(email, password)
                st.success("ログインしました。")
                st.rerun()
            except PermissionError as exc:
                st.error(str(exc))
            except Exception:
                st.error("ログインに失敗しました。")


def _render_dashboard() -> None:
    render_sidebar()
    metrics = _load_dashboard_metrics()
    status_tone, status_icon = _status_badge_theme(metrics["latest_status"])

    render_hero_banner(
        "ダッシュボード",
        "主要指標と最新データを素早く確認できます。",
        eyebrow="研究運用ハブ",
        chips=[
            f"有効品種 {metrics['active_varieties']}種",
            f"レビュー {metrics['active_reviews']}件",
            f"平均評価 {metrics['avg_score']:.2f}/10",
        ],
    )
    render_action_bar(
        title="今日の運用フロー",
        description="取得ログ確認 → 品種管理 → 試食評価 → 分析の順で更新すると運用が安定します。",
        actions=["品種管理", "試食評価", "分析", "研究メモ"],
    )

    render_kpi_cards(
        [
            ("有効品種数", str(metrics["active_varieties"]), None),
            ("有効レビュー数", str(metrics["active_reviews"]), None),
            ("研究メモ数", str(metrics["notes_count"]), None),
            ("直近取得件数", str(metrics["latest_upserted"]), f"状態: {metrics['latest_status']}"),
            ("平均総合評価", f"{metrics['avg_score']:.2f}", "10点満点"),
        ]
    )

    status_col, tips_col = st.columns([1, 2])
    with status_col:
        render_surface(
            f"直近の取り込み件数は <strong>{metrics['latest_upserted']}件</strong> です。",
            title="最新取得ジョブ",
            subtitle="MAFF品種レジストリ同期",
            tone="accent",
            elevated=True,
        )
        render_status_badge(f"ステータス: {metrics['latest_status']}", tone=status_tone, icon=status_icon)
    with tips_col:
        render_info_card(
            "運用ヒント: 新規取得後は <strong>品種管理</strong> で画像と説明を確認し、"
            "必要に応じて補足メモを追記してください。"
        )

    render_section_title("最新レビュー", "直近5件の試食評価を表示します。")
    render_surface("気になる品種は「品種管理」から詳細を確認し、必要なら評価を追記しましょう。", tone="soft")
    reviews = _format_latest_reviews(_load_latest_reviews())
    st.dataframe(reviews, use_container_width=True, hide_index=True)

    render_section_title("最新品種取得ログ", "直近5件のMAFF品種取得結果を表示します。")
    render_surface("失敗件数がある場合は設定ページの診断情報を確認し、再取得の前に環境を点検してください。", tone="soft")
    recent_runs = _format_recent_scrape_runs(_load_recent_scrape_runs())
    st.dataframe(recent_runs, use_container_width=True, hide_index=True)

    render_section_title("主要メニュー", "目的別に画面へ移動できます。")
    menu_items = [
        ("pages/01_varieties.py", "品種管理", "図鑑進捗の確認・品種データ編集・画像管理"),
        ("pages/02_reviews.py", "試食評価", "レビュー登録・履歴確認・復元"),
        ("pages/03_analytics.py", "分析ダッシュボード", "評価傾向と品質指標の可視化"),
        ("pages/04_pedigree.py", "交配図", "親子関係のグラフ確認"),
        ("pages/06_notes.py", "研究メモ", "調査メモや運用ログの蓄積"),
    ]
    for start in range(0, len(menu_items), 3):
        row_items = menu_items[start : start + 3]
        columns = st.columns(len(row_items))
        for column, (path, label, description) in zip(columns, row_items, strict=True):
            with column:
                render_surface(description, title=label, tone="soft")
                st.page_link(path, label=f"{label}を開く")


if st.session_state.get("is_authenticated"):
    _render_dashboard()
else:
    _render_login()
