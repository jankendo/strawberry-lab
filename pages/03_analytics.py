"""Analytics dashboard page."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.components.layout import inject_app_style, render_page_header, render_section_title
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

st.set_page_config(page_title="分析", layout="wide")
require_admin_session()
inject_app_style()
render_sidebar()
render_page_header("分析", "レビューと品種情報をもとに傾向を可視化します。")

varieties = list_active_varieties()
render_section_title("分析条件")
col1, col2, col3, col4 = st.columns(4)
with col1:
    date_from = st.date_input("開始日", value=date.today() - timedelta(days=365))
with col2:
    date_to = st.date_input("終了日", value=date.today())
with col3:
    prefecture = st.selectbox("都道府県", [""] + PREFECTURES)
with col4:
    min_count = st.number_input("最小レビュー数", min_value=1, value=1)
tags_raw = st.text_input("タグ (カンマ区切り)")
tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
selected_varieties = st.multiselect(
    "対象品種",
    [v["id"] for v in varieties],
    format_func=lambda x: next((v["name"] for v in varieties if v["id"] == x), x),
)

df = get_filtered_review_dataframe(
    date_from=date_from,
    date_to=date_to,
    prefecture=prefecture or None,
    tags=tags,
    variety_ids=selected_varieties or None,
)
if df.empty:
    st.info("データがありません。")
    st.stop()

render_section_title("A. レーダーチャート")
radar_df = radar_data(df, min_count, selected_varieties or None)
if radar_df.empty:
    st.info("表示条件に合うデータがありません。")
else:
    radar_long = radar_df.melt(
        id_vars=["variety_id", "variety_name", "review_count"],
        value_vars=["sweetness", "sourness", "aroma", "texture", "appearance"],
        var_name="metric",
        value_name="value",
    )
    fig_radar = px.line_polar(
        radar_long,
        r="value",
        theta="metric",
        color="variety_name",
        line_close=True,
    )
    st.plotly_chart(fig_radar, use_container_width=True)

render_section_title("B. 総合評価ランキング")
ranking_rows = ranking_data(df, min_count)
if ranking_rows:
    st.plotly_chart(
        px.bar(ranking_rows, x="name", y="avg_overall", hover_data=["review_count"]),
        use_container_width=True,
    )
else:
    st.info("ランキング対象がありません。")

render_section_title("C. 月次推移")
ts = monthly_timeseries(df)
fig_ts = go.Figure()
fig_ts.add_trace(go.Scatter(x=ts["month"], y=ts["review_count"], name="レビュー件数"))
fig_ts.add_trace(go.Scatter(x=ts["month"], y=ts["avg_overall"], name="平均総合"))
st.plotly_chart(fig_ts, use_container_width=True)

render_section_title("D. 糖度と総合評価")
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
    st.info("散布図対象がありません。")

render_section_title("E. 都道府県マップ")
st.caption("※ このマップは都道府県・タグフィルタのみ適用し、レビュー日付範囲は適用しません。")
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
        st.info("地図データがありません。")
else:
    st.warning("assets/japan_prefectures.geojson が見つかりません。")

st.download_button(
    "分析用ベースデータCSV",
    data=export_table_csv("reviews"),
    file_name="reviews_export.csv",
    mime="text/csv",
)
