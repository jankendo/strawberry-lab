"""Pedigree graph page."""

from __future__ import annotations

import streamlit as st
from streamlit_plotly_events import plotly_events

from src.components.layout import inject_app_style, render_page_header, render_section_title
from src.components.sidebar import render_sidebar
from src.services.auth_service import require_admin_session
from src.services.pedigree_service import (
    build_figure,
    build_graph,
    fetch_graph_data,
    layered_layout,
    subgraph_by_root,
)

st.set_page_config(page_title="交配図", layout="wide")
require_admin_session()
inject_app_style()
render_sidebar()
render_page_header("交配図", "品種系統を可視化し、ノード選択から品種詳細へ移動できます。")

render_section_title("表示条件")
c1, c2, c3 = st.columns(3)
with c1:
    include_deleted = st.checkbox("削除済みを含む", value=False)
with c2:
    direction = st.selectbox("方向", ["ancestors", "descendants", "both"], index=2)
with c3:
    max_depth = st.slider("最大深さ", 1, 5, 3)

varieties, links = fetch_graph_data(include_deleted=include_deleted)
name_by_id = {v["id"]: v["name"] for v in varieties}
root_id = st.selectbox(
    "起点品種",
    [""] + list(name_by_id.keys()),
    format_func=lambda x: "全体" if not x else name_by_id[x],
)

try:
    graph = build_graph(varieties, links)
except ValueError as exc:
    st.error(str(exc))
    st.stop()

graph = subgraph_by_root(graph, root_id, direction, max_depth)
positions = layered_layout(graph)
review_stats = {}
fig = build_figure(graph, positions, review_stats)
events = plotly_events(fig, click_event=True, key="pedigree_graph")
if events:
    point = events[0]
    point_index = point.get("pointIndex")
    node_ids = list(graph.nodes())
    if point_index is not None and point_index < len(node_ids):
        selected_variety_id = node_ids[point_index]
        st.session_state["selected_variety_id"] = selected_variety_id
        st.switch_page("pages/01_varieties.py")
