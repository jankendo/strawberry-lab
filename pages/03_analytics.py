"""Analytics dashboard page."""

from __future__ import annotations

import json
from datetime import date, timedelta
from html import escape
from pathlib import Path
from typing import Any

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
    render_section_switcher,
    render_sticky_primary_action_anchor,
    render_surface,
)
from src.components.sidebar import render_primary_nav, render_sidebar
from src.components.skeletons import render_card_skeleton, render_chart_skeleton, render_table_skeleton
from src.components.tables import is_mobile_client
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
_CHART_SECTIONS = [
    "A. 総合評価ランキング",
    "B. 月次推移",
    "C. レーダーチャート",
    "D. 糖度と総合評価",
    "E. 都道府県マップ",
]
_CHART_SWITCHER_OPTIONS = [
    ("ランキング", "A. 総合評価ランキング"),
    ("月次推移", "B. 月次推移"),
    ("レーダー", "C. レーダーチャート"),
    ("糖度相関", "D. 糖度と総合評価"),
    ("地図", "E. 都道府県マップ"),
]
_CHART_SWITCHER_MAP = dict(_CHART_SWITCHER_OPTIONS)

_ANALYTICS_APPLIED_FILTERS_KEY = "analytics_applied_filters"
_ANALYTICS_PAYLOAD_KEY = "analytics_analysis_payload"


def _build_filter_state(
    *,
    date_from: date,
    date_to: date,
    prefecture: str,
    min_count: int,
    tags_raw: str,
    selected_varieties: list[str],
) -> dict[str, Any]:
    tags = sorted({token.strip() for token in tags_raw.split(",") if token.strip()})
    return {
        "date_from": date_from,
        "date_to": date_to,
        "prefecture": prefecture or "",
        "min_count": int(min_count),
        "tags": tags,
        "selected_varieties": sorted(str(variety_id) for variety_id in selected_varieties),
    }


def _build_filter_chips(filters: dict[str, Any], variety_name_map: dict[str, str]) -> list[str]:
    variety_ids = [str(variety_id) for variety_id in filters.get("selected_varieties", [])]
    variety_labels = [variety_name_map.get(variety_id, variety_id) for variety_id in variety_ids]
    return [
        f"期間 {filters['date_from']:%Y/%m/%d}〜{filters['date_to']:%Y/%m/%d}",
        f"都道府県 {filters['prefecture'] or 'すべて'}",
        f"最小件数 {int(filters['min_count'])}件",
        f"タグ {', '.join(filters['tags']) if filters['tags'] else '指定なし'}",
        f"品種 {', '.join(variety_labels) if variety_labels else 'すべて'}",
    ]


def _render_filter_chips(chips: list[str]) -> None:
    if not chips:
        return
    st.markdown(
        "".join(f'<span class="sl-context-chip">{escape(chip)}</span>' for chip in chips),
        unsafe_allow_html=True,
    )


def _compact_chart_layout(
    fig: go.Figure,
    *,
    show_legend: bool,
    height: int = 340,
    hovermode: str | None = None,
) -> None:
    layout_config: dict[str, Any] = {
        "height": height,
        "margin": {"l": 8, "r": 8, "t": 24, "b": 8},
        "legend": {
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "left",
            "x": 0,
        },
        "showlegend": show_legend,
        "font": {"size": 12},
    }
    if hovermode:
        layout_config["hovermode"] = hovermode
    fig.update_layout(**layout_config)
    fig.update_xaxes(automargin=True, title_font={"size": 12}, tickfont={"size": 11})
    fig.update_yaxes(automargin=True, title_font={"size": 12}, tickfont={"size": 11})


def _short_label(label: str, *, limit: int = 12) -> str:
    text = str(label)
    return text if len(text) <= limit else f"{text[:limit - 1]}…"


@st.cache_data(ttl=1800)
def _load_prefecture_geojson(path: str) -> dict[str, Any] | None:
    geo_path = Path(path)
    if not geo_path.exists():
        return None
    try:
        geojson = json.loads(geo_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return geojson if geojson.get("features") else {}


def _build_analysis_payload(applied_filters: dict[str, Any]) -> dict[str, Any]:
    selected_varieties = [str(variety_id) for variety_id in applied_filters["selected_varieties"]]
    df = get_filtered_review_dataframe(
        date_from=applied_filters["date_from"],
        date_to=applied_filters["date_to"],
        prefecture=applied_filters["prefecture"] or None,
        tags=applied_filters["tags"] or None,
        variety_ids=selected_varieties or None,
    )
    if df.empty:
        return {"filters": dict(applied_filters), "has_data": False}

    overall_series = df["overall"].dropna() if "overall" in df else pd.Series(dtype="float64")
    prefecture_series = df["origin_prefecture"].dropna() if "origin_prefecture" in df else pd.Series(dtype="object")

    score_columns = [metric for metric in _RADAR_AXIS_LABELS if metric in df.columns]
    score_means = df[score_columns].mean(numeric_only=True) if score_columns else pd.Series(dtype="float64")
    top_metric = str(score_means.idxmax()) if not score_means.empty else "overall"

    return {
        "filters": dict(applied_filters),
        "has_data": True,
        "review_count": int(len(df)),
        "variety_count": int(df["variety_id"].nunique()) if "variety_id" in df else 0,
        "prefecture_count": int(prefecture_series.nunique()),
        "overall_mean": float(overall_series.mean()) if not overall_series.empty else 0.0,
        "analysis_days": max((applied_filters["date_to"] - applied_filters["date_from"]).days + 1, 1),
        "top_metric": top_metric,
        "confidence_hint": "レビュー数が少ないため傾向は暫定です。" if len(df) < 10 else "レビュー数は十分です。",
        "ranking_rows": ranking_data(df, int(applied_filters["min_count"])),
        "timeseries_rows": monthly_timeseries(df).to_dict("records"),
        "radar_rows": radar_data(df, int(applied_filters["min_count"]), selected_varieties or None).to_dict("records"),
        "scatter_rows": scatter_data(df),
    }


def _render_analysis_loading_state(*, is_mobile: bool, message: str) -> None:
    with st.container(border=True):
        render_section_title("分析データを準備中", message)
        render_card_skeleton(count=3 if is_mobile else 4, is_mobile=is_mobile)
        render_chart_skeleton(height=220 if is_mobile else 280, is_mobile=is_mobile)
        render_table_skeleton(rows=3, columns=4, is_mobile=is_mobile)


st.set_page_config(page_title="分析", layout="wide")
require_admin_session()
inject_app_style()
render_sidebar(active_page="analytics")
render_primary_nav(active_page="analytics")
render_hero_banner(
    "分析ダッシュボード",
    "レビューデータを期間・品種・産地で集計し、比較しながら傾向を確認できます。",
    eyebrow="分析インサイト",
    chips=["条件を設定", "分析を実行", "結論を確認", "必要なチャートだけ表示"],
)
mobile_client = is_mobile_client()
varieties = list_active_varieties()
variety_ids = [str(variety["id"]) for variety in varieties]
variety_name_map = {str(variety["id"]): str(variety.get("name") or variety["id"]) for variety in varieties}

saved_filters = st.session_state.get(_ANALYTICS_APPLIED_FILTERS_KEY) or {}
default_date_from = saved_filters.get("date_from")
if not isinstance(default_date_from, date):
    default_date_from = date.today() - timedelta(days=365)
default_date_to = saved_filters.get("date_to")
if not isinstance(default_date_to, date):
    default_date_to = date.today()

prefecture_options = [""] + PREFECTURES
default_prefecture = str(saved_filters.get("prefecture") or "")
prefecture_index = prefecture_options.index(default_prefecture) if default_prefecture in prefecture_options else 0
default_min_count = max(int(saved_filters.get("min_count") or 1), 1)
default_tags_raw = ", ".join(saved_filters.get("tags") or [])
default_varieties = [
    str(variety_id)
    for variety_id in (saved_filters.get("selected_varieties") or [])
    if str(variety_id) in variety_ids
]

with st.container(border=True):
    render_section_title("1) フィルタ")
    date_from = st.date_input("開始日", value=default_date_from)
    date_to = st.date_input("終了日", value=default_date_to)
    prefecture = st.selectbox("都道府県", prefecture_options, index=prefecture_index)
    min_count = st.number_input("最小レビュー件数", min_value=1, value=default_min_count)
    tags_raw = st.text_input("タグ (カンマ区切り)", value=default_tags_raw)
    selected_varieties = st.multiselect(
        "対象品種",
        variety_ids,
        default=default_varieties,
        format_func=lambda variety_id: variety_name_map.get(str(variety_id), str(variety_id)),
    )

current_filters = _build_filter_state(
    date_from=date_from,
    date_to=date_to,
    prefecture=prefecture,
    min_count=int(min_count),
    tags_raw=tags_raw,
    selected_varieties=[str(variety_id) for variety_id in selected_varieties],
)

with st.container(border=True):
    render_section_title("フィルタ状態")
    _render_filter_chips(_build_filter_chips(current_filters, variety_name_map))

invalid_date_range = current_filters["date_from"] > current_filters["date_to"]
with st.container(border=True):
    render_section_title("2) 分析を実行")
    render_sticky_primary_action_anchor("analytics-run")
    run_col, info_col = st.columns([1, 2], gap="large")
    with run_col:
        run_clicked = st.button(
            "分析を実行",
            type="primary",
            use_container_width=True,
            disabled=bool(invalid_date_range),
        )
    with info_col:
        if invalid_date_range:
            st.error("開始日は終了日以前で指定してください。")

analysis_payload = st.session_state.get(_ANALYTICS_PAYLOAD_KEY)
analysis_loading_placeholder = st.empty()
if run_clicked and not invalid_date_range:
    st.session_state[_ANALYTICS_APPLIED_FILTERS_KEY] = current_filters
    with analysis_loading_placeholder.container():
        _render_analysis_loading_state(is_mobile=mobile_client, message="フィルタ条件で集計を実行しています。")
    try:
        analysis_payload = _build_analysis_payload(current_filters)
    finally:
        analysis_loading_placeholder.empty()
    st.session_state[_ANALYTICS_PAYLOAD_KEY] = analysis_payload

applied_filters = st.session_state.get(_ANALYTICS_APPLIED_FILTERS_KEY)
if not applied_filters:
    render_empty_state(
        "フィルタを設定したら「分析を実行」を押してください。",
        title="まだ分析を実行していません",
        hint="実行後に結論サマリーとチャートが表示されます。",
    )
    st.stop()

if not isinstance(analysis_payload, dict) or analysis_payload.get("filters") != applied_filters:
    with analysis_loading_placeholder.container():
        _render_analysis_loading_state(is_mobile=mobile_client, message="保存済み条件の分析結果を復元しています。")
    try:
        analysis_payload = _build_analysis_payload(applied_filters)
    finally:
        analysis_loading_placeholder.empty()
    st.session_state[_ANALYTICS_PAYLOAD_KEY] = analysis_payload

if applied_filters != current_filters:
    render_surface(
        "入力中の条件はまだ分析結果に反映されていません。更新するには「分析を実行」を押してください。",
        title="未反映の変更があります",
        tone="warning",
    )

with st.container(border=True):
    render_section_title("3) 結論とサマリー")
    _render_filter_chips(_build_filter_chips(applied_filters, variety_name_map))

if not analysis_payload.get("has_data"):
    render_empty_state(
        "条件に一致するレビューがありません。",
        title="分析対象がありません",
        hint="期間を広げる・都道府県を「すべて」に戻す・タグを減らす、の順で調整すると改善しやすいです。",
    )
    st.stop()

top_metric_key = str(analysis_payload.get("top_metric") or "overall")
top_metric_label = _RADAR_AXIS_LABELS.get(top_metric_key, top_metric_key)
render_surface(
    (
        f"平均総合評価は **{analysis_payload['overall_mean']:.2f}/10** です。"
        f" 最も高評価な軸は **{top_metric_label}** でした。"
        f"\n\n対象レビュー **{analysis_payload['review_count']}件** / 品種 **{analysis_payload['variety_count']}件** / "
        f"産地 **{analysis_payload['prefecture_count']}件**。"
        f"\n\n{analysis_payload['confidence_hint']}"
    ),
    title="結論サマリー",
    tone="accent",
)

with st.container(border=True):
    render_kpi_cards(
        [
            (
                "対象レビュー",
                f"{analysis_payload['review_count']}件",
                f"{applied_filters['date_from']:%Y/%m/%d}〜{applied_filters['date_to']:%Y/%m/%d}",
            ),
            ("対象品種", f"{analysis_payload['variety_count']}品種", "フィルタ適用後"),
            ("対象都道府県", f"{analysis_payload['prefecture_count']}件", "レビュー対象の産地"),
            ("平均総合評価", f"{analysis_payload['overall_mean']:.2f}", "10点満点"),
            ("分析期間", f"{analysis_payload['analysis_days']}日", None),
        ]
    )

active_chart_label = render_section_switcher(
    [label for label, _ in _CHART_SWITCHER_OPTIONS],
    key="analytics_active_chart",
    title="4) チャート詳細",
    description=None,
    mobile_label="表示チャート",
)
active_chart = _CHART_SWITCHER_MAP.get(active_chart_label, _CHART_SECTIONS[0])

if active_chart == "A. 総合評価ランキング":
    ranking_rows = list(analysis_payload.get("ranking_rows") or [])
    with st.container(border=True):
        render_section_title("A. 総合評価ランキング")
        if len(ranking_rows) < 2:
            render_empty_state(
                "比較対象の品種が不足しているためランキングを省略しました。",
                title="ランキング表示対象なし",
                hint="期間を広げるか、最小レビュー件数を下げて再実行してください。",
            )
        else:
            ranking_df = pd.DataFrame(ranking_rows)
            ranking_df["short_name"] = ranking_df["name"].map(_short_label)
            ranking_df = ranking_df.sort_values(["avg_overall", "review_count"], ascending=[True, True])
            ranking_fig = px.bar(
                ranking_df,
                x="avg_overall",
                y="short_name",
                orientation="h",
                hover_name="name",
                hover_data={"avg_overall": ":.2f", "review_count": True, "short_name": False},
                text="avg_overall",
            )
            ranking_fig.update_traces(texttemplate="%{text:.2f}", textposition="outside", cliponaxis=False)
            ranking_fig.update_layout(yaxis={"title": None, "categoryorder": "total ascending"})
            ranking_fig.update_xaxes(title="平均総合 (10点満点)", range=[0, 10])
            _compact_chart_layout(ranking_fig, show_legend=False, hovermode="y")
            st.plotly_chart(ranking_fig, use_container_width=True)

elif active_chart == "B. 月次推移":
    timeseries_df = pd.DataFrame(analysis_payload.get("timeseries_rows") or [])
    with st.container(border=True):
        render_section_title("B. 月次推移")
        if timeseries_df.empty:
            render_empty_state(
                "時系列データがありません。",
                title="月次推移を表示できません",
                hint="レビュー日を含む条件に変更して再実行してください。",
            )
        else:
            timeseries_df["month"] = pd.to_datetime(timeseries_df["month"])
            active_ts = timeseries_df[timeseries_df["review_count"] > 0].copy()
            if len(active_ts) < 2:
                render_empty_state(
                    "1か月分のみのため傾向比較は省略しました。",
                    title="月次比較データ不足",
                    hint="期間を広げて2か月以上のレビューを含めると推移を確認できます。",
                )
            else:
                fig_ts = go.Figure()
                fig_ts.add_trace(
                    go.Bar(
                        x=active_ts["month"],
                        y=active_ts["review_count"],
                        name="レビュー件数",
                        opacity=0.35,
                        yaxis="y2",
                    )
                )
                fig_ts.add_trace(
                    go.Scatter(
                        x=active_ts["month"],
                        y=active_ts["avg_overall"],
                        name="平均総合",
                        mode="lines+markers",
                        line={"width": 2},
                    )
                )
                fig_ts.update_layout(
                    xaxis_title="月",
                    yaxis={"title": "平均総合", "range": [0, 10]},
                    yaxis2={
                        "title": "件数",
                        "overlaying": "y",
                        "side": "right",
                        "rangemode": "tozero",
                        "showgrid": False,
                    },
                )
                fig_ts.update_xaxes(tickformat="%y/%m", tickangle=-35)
                _compact_chart_layout(fig_ts, show_legend=True, hovermode="x unified")
                st.plotly_chart(fig_ts, use_container_width=True)

elif active_chart == "C. レーダーチャート":
    radar_df = pd.DataFrame(analysis_payload.get("radar_rows") or [])
    with st.container(border=True):
        render_section_title("C. レーダーチャート")
        if radar_df.empty or int(radar_df.get("variety_id", pd.Series(dtype="object")).nunique()) < 2:
            render_empty_state(
                "比較対象の品種が不足しているためレーダーチャートを省略しました。",
                title="レーダーチャート対象不足",
                hint="品種を2つ以上選ぶか、最小レビュー件数を下げて再実行してください。",
            )
        else:
            metric_columns = [metric for metric in _RADAR_AXIS_LABELS if metric in radar_df.columns]
            if not metric_columns:
                render_empty_state(
                    "比較に必要な評価指標が不足しています。",
                    title="レーダーチャートを表示できません",
                )
            else:
                radar_long = radar_df.melt(
                    id_vars=["variety_id", "variety_name", "review_count"],
                    value_vars=metric_columns,
                    var_name="metric",
                    value_name="value",
                )
                radar_long["metric_label"] = radar_long["metric"].map(_RADAR_AXIS_LABELS).fillna(radar_long["metric"])
                radar_long["variety_short"] = radar_long["variety_name"].map(_short_label)
                fig_radar = px.line_polar(
                    radar_long,
                    r="value",
                    theta="metric_label",
                    color="variety_short",
                    line_close=True,
                    category_orders={"metric_label": _RADAR_AXIS_ORDER},
                    hover_name="variety_name",
                )
                fig_radar.update_traces(fill="toself")
                fig_radar.update_layout(
                    polar={"radialaxis": {"range": [0, 10], "tickvals": [2, 4, 6, 8, 10]}},
                    legend_title_text="品種",
                )
                _compact_chart_layout(fig_radar, show_legend=True)
                st.plotly_chart(fig_radar, use_container_width=True)

elif active_chart == "D. 糖度と総合評価":
    scatter_rows = list(analysis_payload.get("scatter_rows") or [])
    with st.container(border=True):
        render_section_title("D. 糖度と総合評価")
        if len(scatter_rows) < 3:
            render_empty_state(
                "有効な糖度データが不足しているため散布図を省略しました。",
                title="散布図データ不足",
                hint="糖度データのある品種を追加するか、期間を広げて再実行してください。",
            )
        else:
            scatter_df = pd.DataFrame(scatter_rows)
            scatter_fig = px.scatter(
                scatter_df,
                x="brix_midpoint",
                y="avg_overall",
                size="review_count",
                hover_name="name",
                color="avg_overall",
                color_continuous_scale="RdYlGn",
                range_y=[0, 10],
            )
            scatter_fig.update_layout(coloraxis_colorbar={"title": "平均総合"})
            scatter_fig.update_xaxes(title="糖度中央値")
            scatter_fig.update_yaxes(title="平均総合")
            _compact_chart_layout(scatter_fig, show_legend=False)
            st.plotly_chart(scatter_fig, use_container_width=True)

elif active_chart == "E. 都道府県マップ":
    with st.container(border=True):
        render_section_title("E. 都道府県マップ")
        st.caption("地図は都道府県・タグ条件のみを反映します。")
        map_counts = prefecture_counts(
            prefecture=applied_filters["prefecture"] or None,
            tags=applied_filters["tags"] or None,
        )
        map_df = pd.DataFrame(
            [
                {"prefecture": prefecture_name, "count": count}
                for prefecture_name, count in map_counts.items()
            ]
        )
        if map_df.empty or len(map_df) < 2:
            message = "都道府県が1件以下のため地図比較を省略しました。"
            if not map_df.empty:
                top_row = map_df.sort_values("count", ascending=False).iloc[0]
                message = f"現在は **{top_row['prefecture']}** のみ対象です（{int(top_row['count'])}件）。"
            render_empty_state(
                message,
                title="地図比較データ不足",
                hint="都道府県を「すべて」に戻すか、タグ条件を緩めて再実行してください。",
            )
        else:
            geojson = _load_prefecture_geojson("assets/japan_prefectures.geojson")
            if geojson is None:
                st.warning("assets/japan_prefectures.geojson が見つかりません。")
            elif not geojson.get("features"):
                render_empty_state("地図データを読み込めませんでした。", title="地図表示対象なし")
            else:
                fig_map = px.choropleth(
                    map_df,
                    geojson=geojson,
                    featureidkey="properties.name",
                    locations="prefecture",
                    color="count",
                )
                fig_map.update_geos(fitbounds="locations", visible=False)
                fig_map.update_layout(coloraxis_colorbar={"title": "品種数"})
                _compact_chart_layout(fig_map, show_legend=False, height=380)
                st.plotly_chart(fig_map, use_container_width=True)

with st.container(border=True):
    render_section_title("分析データの出力")
    if st.toggle("分析用CSVを準備する", value=False, key="analytics_prepare_export"):
        st.download_button(
            "分析用ベースデータCSV",
            data=export_table_csv("reviews"),
            file_name="reviews_export.csv",
            mime="text/csv",
            use_container_width=True,
            type="primary",
        )
