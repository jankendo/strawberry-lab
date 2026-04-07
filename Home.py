"""StrawberryLab home page."""

from __future__ import annotations

import streamlit as st

from src.components.layout import inject_app_style, render_page_header, render_section_title
from src.components.sidebar import render_primary_nav, render_sidebar
from src.components.skeletons import render_card_skeleton, render_table_skeleton
from src.components.tables import is_mobile_client, render_table
from src.services.auth_service import (
    ensure_auth_cookie_persistence,
    get_auth_persistence_status,
    get_user_client,
    initialize_auth_state,
    login_user,
    restore_login_from_cookie,
)
from src.services.cache_service import scoped_cache_data

try:
    from src.components.layout import (
        render_action_bar,
        render_empty_state,
        render_hero_banner,
        render_info_card,
        render_kpi_cards,
        render_lead,
        render_section_switcher,
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

    def render_empty_state(
        message: str,
        *,
        title: str = "表示できるデータがありません",
        hint: str | None = None,
        action_label: str | None = None,
        action_path: str | None = None,
    ) -> None:
        """Fallback empty-state renderer for partially refreshed runtimes."""
        if title:
            st.caption(title)
        st.info(" ".join(part for part in [message, hint] if part))
        if action_label and action_path:
            st.page_link(action_path, label=action_label, use_container_width=True)


    def render_kpi_cards(items: list[tuple[str, str, str | None]], *, per_row: int = 4) -> None:
        """Fallback KPI renderer for partially refreshed runtimes."""
        _ = per_row
        columns = st.columns(len(items))
        for column, (label, value, sub_text) in zip(columns, items, strict=True):
            column.metric(label, value, help=sub_text)


    def render_section_switcher(
        options: list[str],
        *,
        key: str,
        title: str = "表示セクション",
        description: str | None = None,
        mobile_label: str | None = None,
    ) -> str:
        """Fallback section switcher for partially refreshed runtimes."""
        _ = title, description
        active_value = str(st.session_state.get(key) or options[0])
        if active_value not in options:
            active_value = options[0]
        return str(
            st.selectbox(
                mobile_label or "表示セクション",
                options,
                index=options.index(active_value),
                key=key,
            )
        )


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


@scoped_cache_data(ttl=120, scopes=("varieties", "reviews", "scrape"))
def _load_dashboard_metrics() -> dict:
    client = get_user_client()
    if client is None:
        return {
            "active_varieties": 0,
            "active_reviews": 0,
            "avg_score": 0.0,
            "avg_score_sample_size": 0,
            "latest_status": "-",
            "latest_upserted": 0,
        }

    active_varieties = (
        client.table("varieties").select("id", count="exact", head=True).is_("deleted_at", "null").execute().count or 0
    )
    active_reviews = (
        client.table("reviews").select("id", count="exact", head=True).is_("deleted_at", "null").execute().count or 0
    )
    recent_score_rows = (
        client.table("reviews")
        .select("overall")
        .is_("deleted_at", "null")
        .order("tasted_date", desc=True)
        .limit(60)
        .execute()
        .data
        or []
    )
    score_values = [row.get("overall") for row in recent_score_rows if row.get("overall") is not None]
    avg_score = round(sum(score_values) / len(score_values), 2) if score_values else 0
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
        "avg_score": float(avg_score),
        "avg_score_sample_size": len(score_values),
        "latest_status": latest_scrape[0]["status"] if latest_scrape else "-",
        "latest_upserted": int(latest_scrape[0]["upserted_count"]) if latest_scrape else 0,
    }


@scoped_cache_data(ttl=120, scopes="reviews")
def _load_latest_reviews(limit: int = 4) -> list[dict]:
    client = get_user_client()
    if client is None:
        return []
    return (
        client.table("reviews")
        .select("tasted_date,overall,varieties(name)")
        .is_("deleted_at", "null")
        .order("tasted_date", desc=True)
        .limit(limit)
        .execute()
        .data
        or []
    )


@scoped_cache_data(ttl=120, scopes="scrape")
def _load_recent_scrape_runs(limit: int = 4) -> list[dict]:
    client = get_user_client()
    if client is None:
        return []
    return (
        client.table("variety_scrape_runs")
        .select("started_at,finished_at,status,upserted_count,failed_count")
        .order("started_at", desc=True)
        .limit(limit)
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
            "状態": f"{_status_badge_theme(row.get('status') or '-')[1]} {row.get('status') or '-'}",
            "更新件数": row.get("upserted_count") or 0,
            "失敗件数": row.get("failed_count") or 0,
        }
        for row in rows
    ]


def _build_today_tasks(metrics: dict, *, status_tone: str) -> list[tuple[str, str, str]]:
    pending_reviews = max(int(metrics["active_varieties"]) - int(metrics["active_reviews"]), 0)
    tasks: list[tuple[str, str, str]] = []

    if status_tone == "danger":
        tasks.append(
            (
                "⚙️ 取得エラーを確認",
                "最新取得が失敗しています。設定ページで実行履歴とエラー内容を確認してください。",
                "pages/07_settings.py",
            )
        )
    variety_title = (
        f"🍓 未評価候補を整理（{pending_reviews}件）"
        if pending_reviews > 0
        else "🍓 品種データを確認"
    )
    variety_hint = (
        "今日レビューする候補を品種管理で確認します。"
        if pending_reviews > 0
        else "新規品種や更新対象がないかを品種管理で確認します。"
    )
    tasks.append((variety_title, variety_hint, "pages/01_varieties.py"))

    tasks.append(
        (
            "📝 試食レビューを登録",
            "今日の評価を登録して分析に反映します。",
            "pages/02_reviews.py",
        )
    )
    tasks.append(
        (
            "📊 分析を確認",
            "最新レビューの傾向を確認します。",
            "pages/03_analytics.py",
        )
    )
    return tasks[:3]


def _render_dashboard_loading_skeleton(*, is_mobile: bool, include_feed: bool) -> None:
    with st.container(border=True):
        st.caption("ダッシュボードを読み込んでいます…")
        render_card_skeleton(count=3 if is_mobile else 5, is_mobile=is_mobile)
    if include_feed:
        with st.container(border=True):
            st.caption("最新データを取得しています…")
            render_table_skeleton(rows=4, columns=4, is_mobile=is_mobile)


def _render_login() -> None:
    persistence = get_auth_persistence_status()
    mobile_client = is_mobile_client()
    render_hero_banner(
        "StrawberryLab",
        "いちご品種の研究・評価を一元管理するための管理アプリです。"
        if not mobile_client
        else "ログインして管理ワークスペースを利用します。",
        eyebrow="管理者ワークスペース",
        chips=["ログインが必要です", "30日ログイン保持対応"],
    )
    if not mobile_client:
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
        if mobile_client:
            render_status_badge("30日ログイン保持: 有効", tone="success", icon="✅")
        else:
            st.caption("✅ 30日ログイン保持: 有効")
    elif persistence["code"] in {"missing_secret", "cookie_manager_not_ready_ephemeral_secret"}:
        st.warning(f"⚠️ {persistence['message']} `.streamlit/secrets.toml` を確認してください。")
    else:
        if mobile_client:
            render_status_badge(persistence["message"], tone="info", icon="ℹ️")
        else:
            st.caption(f"ℹ️ {persistence['message']}")

    if mobile_client:
        form_container = st.container()
    else:
        _, center, _ = st.columns([1, 1.4, 1])
        form_container = center

    with form_container:
        if mobile_client:
            st.markdown("### ログイン")
            st.caption("アクセス権限を持つアカウントのみ利用できます。")
        else:
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
    render_sidebar(active_page="dashboard")
    render_primary_nav(active_page="dashboard")
    mobile_client = is_mobile_client()

    render_hero_banner(
        "ダッシュボード",
        (
            "最優先の作業を上から順に実行できます。"
            if mobile_client
            else "今日の状況 → 今日やること → 最新ログの順で、必要な操作だけ進めます。"
        ),
        eyebrow="今日のワークフロー",
        chips=["優先タスク", "状況サマリー", "更新ログ"],
    )
    if not mobile_client:
        render_action_bar(
            title="今日の見方",
            description="上から順に確認すると、必要な判断と次アクションが最短で分かります。",
            actions=["今日の状況", "今日やること", "更新ログ"],
        )

    metrics_loading_placeholder = st.empty()
    with metrics_loading_placeholder.container():
        _render_dashboard_loading_skeleton(is_mobile=mobile_client, include_feed=False)
    try:
        metrics = _load_dashboard_metrics()
    finally:
        metrics_loading_placeholder.empty()

    pending_reviews = max(metrics["active_varieties"] - metrics["active_reviews"], 0)
    status_tone, status_icon = _status_badge_theme(metrics["latest_status"])
    average_hint = (
        f"直近{metrics['avg_score_sample_size']}件"
        if metrics["avg_score_sample_size"] > 0
        else "レビュー未登録"
    )

    today_tasks = _build_today_tasks(metrics, status_tone=status_tone)
    if mobile_client:
        render_section_title("今日やること")
    else:
        render_section_title("今日の状況")
        render_kpi_cards(
            [
                ("有効品種数", str(metrics["active_varieties"]), None),
                ("未評価候補", str(pending_reviews), "レビュー待ち"),
                ("有効レビュー数", str(metrics["active_reviews"]), None),
                ("直近取得件数", str(metrics["latest_upserted"]), f"状態: {metrics['latest_status']}"),
                ("直近評価平均", f"{metrics['avg_score']:.2f}", average_hint),
            ],
            per_row=5,
        )
        render_status_badge(f"最新取得ステータス: {metrics['latest_status']}", tone=status_tone, icon=status_icon)
        render_section_title("今日やること", "上から順に実行すると進捗が止まりにくくなります。")

    for index, (title, hint, path) in enumerate(today_tasks, start=1):
        with st.container(border=True):
            render_status_badge(f"優先 {index}", tone="info", icon="➡️")
            st.markdown(f"**{title}**")
            st.caption(hint)
            st.page_link(path, label="この作業を開く", use_container_width=True)

    if mobile_client:
        render_section_title("今日の状況")
        render_kpi_cards(
            [
                ("有効品種数", str(metrics["active_varieties"]), None),
                ("未評価候補", str(pending_reviews), "レビュー待ち"),
                ("有効レビュー数", str(metrics["active_reviews"]), None),
                ("直近取得件数", str(metrics["latest_upserted"]), f"状態: {metrics['latest_status']}"),
                ("直近評価平均", f"{metrics['avg_score']:.2f}", average_hint),
            ],
            per_row=5,
        )
        render_status_badge(f"最新取得ステータス: {metrics['latest_status']}", tone=status_tone, icon=status_icon)

    feed_view = render_section_switcher(
        ["最新レビュー", "最新取得ログ"],
        key="dashboard_feed_view",
        title="最新レビュー / 最新取得ログ",
        description=None if mobile_client else "初期表示は1つだけ読み込み、必要時に切り替えます。",
        mobile_label="更新情報",
    )

    if feed_view == "最新レビュー":
        feed_loading_placeholder = st.empty()
        with feed_loading_placeholder.container():
            render_table_skeleton(rows=4, columns=3, is_mobile=mobile_client)
        try:
            reviews = _format_latest_reviews(_load_latest_reviews(limit=4))
        finally:
            feed_loading_placeholder.empty()
        if reviews:
            render_table(
                reviews,
                mobile_title_key="品種名",
                mobile_subtitle_key="試食日",
                mobile_metadata_keys=["総合評価"],
            )
        else:
            render_empty_state(
                "評価データが登録されていないため、最新レビューを表示できません。",
                title="最新レビューはまだありません",
                hint="まずは1件レビューを登録すると、ここに時系列で表示されます。",
                action_label="📝 試食評価ページを開く",
                action_path="pages/02_reviews.py",
            )
    else:
        render_status_badge(f"ステータス: {metrics['latest_status']}", tone=status_tone, icon=status_icon)
        feed_loading_placeholder = st.empty()
        with feed_loading_placeholder.container():
            render_table_skeleton(rows=4, columns=5, is_mobile=mobile_client)
        try:
            recent_runs = _format_recent_scrape_runs(_load_recent_scrape_runs(limit=4))
        finally:
            feed_loading_placeholder.empty()
        if recent_runs:
            render_table(
                recent_runs,
                mobile_title_key="状態",
                mobile_subtitle_key="開始日時",
                mobile_metadata_keys=["終了日時", "更新件数", "失敗件数"],
            )
        else:
            render_empty_state(
                "取得ジョブがまだ実行されていないため、履歴を表示できません。",
                title="取得ログはまだありません",
                hint="設定ページで取得を実行すると、最新ログがここに表示されます。",
                action_label="⚙️ 設定ページを開く",
                action_path="pages/07_settings.py",
            )


if st.session_state.get("is_authenticated"):
    _render_dashboard()
else:
    _render_login()
