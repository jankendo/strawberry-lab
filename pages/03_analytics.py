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
render_sidebar()
render_hero_banner(
    "分析ダッシュボード",
    "レビューと品種データを横断し、味覚傾向・評価推移・産地分布を立体的に確認できます。",
    eyebrow="分析インサイト",
    chips=["期間比較", "品種ランキング", "地域分布", "CSV出力"],
)
render_action_bar(
    title="分析の進め方",
    description="条件を絞り込んだあと、各チャートで比較し、最後にCSVで出力してください。",
    actions=["期間を設定", "タグで絞り込み", "品種を比較", "結果を共有"],
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
tags = [t.strip() for t in tags_raw.split(",") if t.strip()]

df = get_filtered_review_dataframe(
    date_from=date_from,
    date_to=date_to,
    prefecture=prefecture or None,
    tags=tags,
    variety_ids=selected_varieties or None,
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
            ("対象レビュー", f"{len(df)}件", f"{date_from:%Y/%m/%d}〜{date_to:%Y/%m/%d}"),
            ("対象品種", f"{int(df['variety_id'].nunique())}件", "フィルタ適用後"),
            ("対象都道府県", f"{int(prefecture_series.nunique())}件", "レビュー対象の産地"),
            ("平均総合評価", f"{float(overall_series.mean()) if not overall_series.empty else 0.0:.2f}", "10点満点"),
            ("分析期間", f"{max((date_to - date_from).days + 1, 1)}日", None),
        ]
    )

with st.container(border=True):
    render_section_title("A. レーダーチャート", "味覚5指標の平均値を品種ごとに比較します。")
    radar_df = radar_data(df, min_count, selected_varieties or None)
    if radar_df.empty:
        render_empty_state("表示条件に合うデータがありません。", title="レーダーチャート対象なし")
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

with st.container(border=True):
    render_section_title("B. 総合評価ランキング", "平均総合評価とレビュー件数の上位傾向を確認します。")
    ranking_rows = ranking_data(df, min_count)
    if ranking_rows:
        st.plotly_chart(
            px.bar(ranking_rows, x="name", y="avg_overall", hover_data=["review_count"]),
            use_container_width=True,
        )
    else:
        render_empty_state("ランキング対象がありません。", title="ランキング対象なし")

with st.container(border=True):
    render_section_title("C. 月次推移", "レビュー件数と平均総合評価の時系列変化です。")
    ts = monthly_timeseries(df)
    fig_ts = go.Figure()
    fig_ts.add_trace(go.Scatter(x=ts["month"], y=ts["review_count"], name="レビュー件数"))
    fig_ts.add_trace(go.Scatter(x=ts["month"], y=ts["avg_overall"], name="平均総合"))
    st.plotly_chart(fig_ts, use_container_width=True)

with st.container(border=True):
    render_section_title("D. 糖度と総合評価", "糖度の中央値と総合評価の関係を散布図で確認します。")
    scatter_rows = scatter_data(df)
    if scatter_rows:
        st.plotly_chart(
            px.scatter(
                scatter_rows,
                x="brix_midpoint",
                y="avg_overall",
                size="review_count",
                hover_name="name",
            ),
            use_container_width=True,
        )
    else:
        render_empty_state("散布図対象がありません。", title="散布図対象なし")

with st.container(border=True):
    render_section_title("E. 都道府県マップ", "都道府県別の品種分布をヒートマップで表示します。")
    render_surface("※ このマップは都道府県・タグフィルタのみ適用し、レビュー日付範囲は適用しません。", tone="soft")
    geo_path = Path("assets/japan_prefectures.geojson")
    if geo_path.exists():
        geojson = json.loads(geo_path.read_text(encoding="utf-8"))
        pcounts = prefecture_counts(prefecture=prefecture or None, tags=tags)
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
