"""Analytics dashboard page."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.components.layout import (
    inject_app_style,
    render_action_bar,
    render_empty_state,
    render_hero_banner,
    render_kpi_cards,
    render_section_title,
    render_surface,
)
from src.components.sidebar import render_sidebar
from src.constants.prefectures import PREFECTURES
from src.services.analytics_service import (
    get_filtered_review_dataframe,
    monthly_timeseries,
    prefecture_counts,
    radar_data,
    ranking_data,
    scatter_data,
)
from src.services.auth_service import require_admin_session
from src.services.export_service import export_table_csv
from src.services.variety_service import list_active_varieties

_RADAR_AXIS_LABELS = {
    "sweetness": "甘味",
    "sourness": "酸味",
    "aroma": "香り",
    "texture": "食感",
    "appearance": "見た目",
}
_RADAR_AXIS_ORDER = ["甘味", "酸味", "香り", "食感", "見た目"]

st.set_page_config(page_title="分析", layout="wide")
require_admin_session()
inject_app_style()
render_sidebar(active_page="analytics")
render_hero_banner(
    "分析ダッシュボード",
    "条件を明示して分析を実行し、チャートと結論要約で判断できる画面に再構成しました。",
    eyebrow="分析インサイト",
    chips=["条件チップ表示", "分析実行", "ランキング上位10", "結論要約"],
)
render_action_bar(
    title="分析の進め方",
    description="条件を変更したら「分析を実行」を押して結果を更新してください。",
    actions=["期間を設定", "タグで絞り込み", "分析を実行", "結果を確認"],
)

varieties = list_active_varieties()
variety_name_map = {str(v["id"]): str(v.get("name") or v["id"]) for v in varieties}
with st.container(border=True):
    render_section_title("分析条件", "期間・地域・タグ・品種を指定して分析対象を整えます。")
    col1, col2, col3, col4 = st.columns(4, gap="large")
    with col1:
        date_from = st.date_input("開始日", value=date.today() - timedelta(days=365))
    with col2:
        date_to = st.date_input("終了日", value=date.today())
    with col3:
        prefecture = st.selectbox("都道府県", [""] + PREFECTURES)
    with col4:
        min_count = st.number_input("最小レビュー件数", min_value=1, value=1)

    tags_col, varieties_col = st.columns([1, 2], gap="large")
    with tags_col:
        tags_raw = st.text_input("タグ (カンマ区切り)")
    with varieties_col:
        selected_varieties = st.multiselect(
            "対象品種",
            [v["id"] for v in varieties],
            format_func=lambda x: variety_name_map.get(str(x), str(x)),
        )
    execute_col, info_col = st.columns([1, 3], gap="large")
    with execute_col:
        run_clicked = st.button("分析を実行", type="primary", use_container_width=True)
    with info_col:
        st.caption("※ フィルタを変更しただけでは結果は更新されません。分析を実行すると反映されます。")

tags = sorted({t.strip() for t in tags_raw.split(",") if t.strip()})
selected_varieties = sorted(selected_varieties)
if date_from > date_to:
    st.error("開始日は終了日以前で指定してください。")
    st.stop()
current_filters = {
    "date_from": date_from,
    "date_to": date_to,
    "prefecture": prefecture or "",
    "min_count": int(min_count),
    "tags": tags,
    "selected_varieties": selected_varieties,
}
if run_clicked:
    st.session_state["analytics_applied_filters"] = current_filters

applied_filters = st.session_state.get("analytics_applied_filters")
if not applied_filters:
    render_empty_state(
        "分析条件を設定し、「分析を実行」を押してください。",
        title="まだ分析を実行していません",
        hint="初回実行後にランキング・推移・比較チャートが表示されます。",
    )
    st.stop()

if applied_filters != current_filters:
    render_surface("フィルタを変更しました。反映するには「分析を実行」を押してください。", title="未反映の変更があります", tone="warning")

chip_texts = [
    f"期間 {applied_filters['date_from']:%Y/%m/%d}〜{applied_filters['date_to']:%Y/%m/%d}",
    f"都道府県 {applied_filters['prefecture'] or 'すべて'}",
    f"最小件数 {applied_filters['min_count']}件",
    f"タグ {', '.join(applied_filters['tags']) if applied_filters['tags'] else '指定なし'}",
    (
        "品種 "
        + ", ".join(variety_name_map.get(str(variety_id), str(variety_id)) for variety_id in applied_filters["selected_varieties"])
        if applied_filters["selected_varieties"]
        else "品種 すべて"
    ),
]
st.markdown(
    "".join(f'<span class="sl-context-chip">{chip}</span>' for chip in chip_texts),
    unsafe_allow_html=True,
)

df = get_filtered_review_dataframe(
    date_from=applied_filters["date_from"],
    date_to=applied_filters["date_to"],
    prefecture=applied_filters["prefecture"] or None,
    tags=applied_filters["tags"] or None,
    variety_ids=applied_filters["selected_varieties"] or None,
)
if df.empty:
    render_empty_state(
        "データがありません。",
        title="分析対象がありません",
        hint="期間・地域・タグ・品種の条件を調整して再実行してください。",
    )
    st.stop()

overall_series = df["overall"].dropna() if "overall" in df else pd.Series(dtype="float64")
prefecture_series = df["origin_prefecture"].dropna() if "origin_prefecture" in df else pd.Series(dtype="object")
with st.container(border=True):
    render_kpi_cards(
        [
            ("対象レビュー", f"{len(df)}件", f"{applied_filters['date_from']:%Y/%m/%d}〜{applied_filters['date_to']:%Y/%m/%d}"),
            ("対象品種", f"{int(df['variety_id'].nunique())}件", "フィルタ適用後"),
            ("対象都道府県", f"{int(prefecture_series.nunique())}件", "レビュー対象の産地"),
            ("平均総合評価", f"{float(overall_series.mean()) if not overall_series.empty else 0.0:.2f}", "10点満点"),
            ("分析期間", f"{max((applied_filters['date_to'] - applied_filters['date_from']).days + 1, 1)}日", None),
        ]
    )

score_columns = ["sweetness", "sourness", "aroma", "texture", "appearance"]
score_means = df[score_columns].mean(numeric_only=True)
top_metric = score_means.idxmax() if not score_means.empty else "overall"
confidence_hint = "レビュー数が少ないため傾向は暫定です。" if len(df) < 10 else "レビュー数は十分です。"
render_surface(
    f"最も高評価なのは **{_RADAR_AXIS_LABELS.get(top_metric, top_metric)}** です。"
    f" 平均総合評価は **{float(overall_series.mean()) if not overall_series.empty else 0.0:.2f}/10**。"
    f" {confidence_hint}",
    title="分析の結論要約",
    tone="accent",
)

chart_left, chart_right = st.columns(2, gap="large")
with chart_left:
    with st.container(border=True):
        render_section_title("A. 総合評価ランキング", "上位10品種を表示します。")
        ranking_rows = ranking_data(df, int(applied_filters["min_count"]))
        if ranking_rows:
            ranking_fig = px.bar(ranking_rows, x="name", y="avg_overall", hover_data=["review_count"])
            ranking_fig.update_layout(xaxis_title="品種", yaxis_title="平均総合評価")
            st.plotly_chart(ranking_fig, use_container_width=True)
        else:
            render_empty_state("ランキング対象がありません。", title="ランキング対象なし")

with chart_right:
    with st.container(border=True):
        render_section_title("B. 月次推移", "レビュー件数と平均総合評価の時系列です。")
        ts = monthly_timeseries(df)
        fig_ts = go.Figure()
        fig_ts.add_trace(go.Scatter(x=ts["month"], y=ts["review_count"], name="レビュー件数", mode="lines+markers"))
        fig_ts.add_trace(go.Scatter(x=ts["month"], y=ts["avg_overall"], name="平均総合", mode="lines+markers"))
        fig_ts.update_layout(xaxis_title="月", yaxis_title="値")
        st.plotly_chart(fig_ts, use_container_width=True)

bottom_left, bottom_right = st.columns(2, gap="large")
with bottom_left:
    with st.container(border=True):
        render_section_title("C. レーダーチャート", "2品種以上の比較時のみ表示します。")
        radar_df = radar_data(df, int(applied_filters["min_count"]), applied_filters["selected_varieties"] or None)
        if radar_df.empty or int(radar_df["variety_id"].nunique()) < 2:
            render_empty_state(
                "比較対象が2品種以上になるよう条件を調整してください。",
                title="レーダーチャート対象不足",
            )
        else:
            radar_long = radar_df.melt(
                id_vars=["variety_id", "variety_name", "review_count"],
                value_vars=["sweetness", "sourness", "aroma", "texture", "appearance"],
                var_name="metric",
                value_name="value",
            )
            radar_long["metric_label"] = radar_long["metric"].map(_RADAR_AXIS_LABELS).fillna(radar_long["metric"])
            fig_radar = px.line_polar(
                radar_long,
                r="value",
                theta="metric_label",
                color="variety_name",
                line_close=True,
                category_orders={"metric_label": _RADAR_AXIS_ORDER},
            )
            st.plotly_chart(fig_radar, use_container_width=True)

with bottom_right:
    with st.container(border=True):
        render_section_title("D. 糖度と総合評価", "糖度データのある品種のみ散布図表示します。")
        scatter_rows = scatter_data(df)
        if scatter_rows:
            scatter_fig = px.scatter(
                scatter_rows,
                x="brix_midpoint",
                y="avg_overall",
                size="review_count",
                hover_name="name",
            )
            scatter_fig.update_layout(xaxis_title="糖度中央値", yaxis_title="平均総合評価")
            st.plotly_chart(scatter_fig, use_container_width=True)
        else:
            render_surface("糖度データが不足しているため散布図は表示しません。", tone="soft")

with st.container(border=True):
    render_section_title("E. 都道府県マップ", "都道府県別の品種分布を表示します。")
    render_surface("※ 地図は都道府県・タグ条件のみ適用し、レビュー日付範囲は適用しません。", tone="soft")
    geo_path = Path("assets/japan_prefectures.geojson")
    if geo_path.exists():
        geojson = json.loads(geo_path.read_text(encoding="utf-8"))
        pcounts = prefecture_counts(prefecture=applied_filters["prefecture"] or None, tags=applied_filters["tags"] or None)
        map_df = pd.DataFrame([{"prefecture": p, "count": c} for p, c in pcounts.items()])
        if not map_df.empty and geojson.get("features"):
            fig_map = px.choropleth(
                map_df,
                geojson=geojson,
                featureidkey="properties.name",
                locations="prefecture",
                color="count",
            )
            fig_map.update_geos(fitbounds="locations", visible=False)
            st.plotly_chart(fig_map, use_container_width=True)
        else:
            render_empty_state("地図データがありません。", title="地図表示対象なし")
    else:
        st.warning("assets/japan_prefectures.geojson が見つかりません。")

with st.container(border=True):
    render_section_title("分析データの出力", "レビュー原データをCSV形式でダウンロードできます。")
    st.download_button(
        "分析用ベースデータCSV",
        data=export_table_csv("reviews"),
        file_name="reviews_export.csv",
        mime="text/csv",
        use_container_width=True,
        type="primary",
    )
