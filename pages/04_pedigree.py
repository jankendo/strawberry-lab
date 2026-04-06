"""Pedigree graph page."""

from __future__ import annotations

import streamlit as st
from streamlit_plotly_events import plotly_events

from src.components.layout import (
    inject_app_style,
    render_action_bar,
    render_empty_state,
    render_hero_banner,
    render_kpi_cards,
    render_section_title,
    render_status_badge,
    render_surface,
)
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
render_sidebar(active_page="pedigree")
render_hero_banner(
    "交配図",
    "品種系統をネットワークで可視化し、起点指定や深さ制御で必要な系譜だけを素早く確認できます。",
    eyebrow="系統ネットワーク",
    chips=["起点品種指定", "祖先/子孫切替", "ノードクリック遷移"],
)
render_action_bar(
    title="推奨ワークフロー",
    description="親子リンクを整備したうえで、表示条件を調整し、気になるノードをクリックして詳細確認します。",
    actions=["起点品種を選ぶ", "表示方向を切り替える", "最大深さを調整する", "ノードから詳細へ移動"],
)

with st.expander("交配図の使い方", expanded=False):
    st.markdown(
        """
        1. まず **品種管理 > 作成・編集** で親品種リンクを登録  
        2. 交配図で **起点品種 / 表示方向 / 最大深さ** を設定  
        3. ノードをクリックして右パネルで詳細確認  
        """
    )

render_section_title("表示条件", "見たい系譜だけに絞って可視化します。")
c1, c2, c3, c4 = st.columns(4)
with c1:
    include_deleted = st.checkbox("削除済みを含む", value=False)
with c2:
    direction_map = {
        "祖先を表示": "ancestors",
        "子孫を表示": "descendants",
        "祖先＋子孫を表示": "both",
    }
    direction_label = st.selectbox("表示方向", list(direction_map.keys()), index=2)
    direction = direction_map[direction_label]
with c3:
    max_depth = st.slider("最大深さ", 1, 5, 3)
with c4:
    max_nodes = st.slider("最大表示ノード数", 50, 120, 80, step=10)

varieties, links = fetch_graph_data(include_deleted=include_deleted)
if not links:
    render_empty_state(
        "親子リンクが未登録のため交配図を表示できません。",
        title="交配図の表示対象がありません",
        hint="まず品種管理で親品種リンクを登録してください。",
        action_label="🍓 品種管理で親品種を登録",
        action_path="pages/01_varieties.py",
    )
    st.stop()

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

if graph.number_of_edges() == 0:
    render_empty_state(
        "親子リンク数が0件です。",
        title="交配図を表示できません",
        hint="品種管理で親品種リンクを登録してください。",
        action_label="🍓 品種管理を開く",
        action_path="pages/01_varieties.py",
    )
    st.stop()

if not root_id and graph.number_of_nodes() > max_nodes:
    render_empty_state(
        f"全体表示はノード数が多すぎます（{graph.number_of_nodes()}件）。",
        title="起点品種を選択してください",
        hint=f"起点品種を選ぶか、表示ノード数上限（現在 {max_nodes}）を調整してください。",
    )
    st.stop()

graph = subgraph_by_root(graph, root_id, direction, max_depth)
if graph.number_of_nodes() == 0:
    render_empty_state(
        "条件に一致する系統データがありません。",
        title="交配図の表示対象がありません",
        hint="起点品種・表示方向・最大深さを調整して再表示してください。",
    )
    st.stop()

if graph.number_of_nodes() > max_nodes:
    ordered_nodes = [root_id] + [node for node in graph.nodes() if node != root_id] if root_id else list(graph.nodes())
    graph = graph.subgraph(ordered_nodes[:max_nodes]).copy()
    render_surface(f"表示ノード数を {max_nodes} 件に制限しました。", title="表示上限を適用", tone="warning")

positions = layered_layout(graph)
review_stats = {}
fig = build_figure(graph, positions, review_stats)
root_name = "全体" if not root_id else name_by_id.get(root_id, root_id)
render_kpi_cards(
    [
        ("表示ノード数", str(graph.number_of_nodes()), "現在の条件で可視化"),
        ("表示リンク数", str(graph.number_of_edges()), "親子リンク"),
        ("起点品種", root_name, direction_label),
        ("最大深さ", str(max_depth), "探索範囲"),
    ]
)

render_section_title("交配グラフ", "fit-to-viewで初期表示。ドラッグ移動・ホイール拡大縮小ができます。")
graph_col, detail_col = st.columns([3, 1.2], gap="large")
with graph_col:
    graph_height = int(fig.layout.height) if fig.layout.height else 720
    events = plotly_events(
        fig,
        click_event=True,
        key="pedigree_graph",
        override_height=graph_height,
        override_width="100%",
    )
    if events:
        point = events[0]
        selected_variety_id = point.get("customdata")
        if selected_variety_id is None and point.get("curveNumber") in (None, 1):
            point_index = point.get("pointIndex")
            node_ids = list(graph.nodes())
            if isinstance(point_index, int) and 0 <= point_index < len(node_ids):
                selected_variety_id = node_ids[point_index]
        if selected_variety_id and selected_variety_id in graph:
            st.session_state["pedigree_selected_node"] = selected_variety_id
            st.rerun()

with detail_col:
    selected_node = st.session_state.get("pedigree_selected_node")
    if selected_node and selected_node in graph:
        with st.container(border=True):
            st.markdown(f"**{name_by_id.get(selected_node, selected_node)}**")
            render_status_badge("選択中ノード", tone="info")
            st.caption(f"親ノード数: {graph.in_degree(selected_node)}")
            st.caption(f"子ノード数: {graph.out_degree(selected_node)}")
            if st.button("品種詳細を開く", key="open_selected_pedigree_node", use_container_width=True, type="primary"):
                st.session_state["selected_variety_id"] = selected_node
                st.switch_page("pages/01_varieties.py")
    else:
        render_surface("ノードをクリックすると詳細をここに表示します。", title="ノード詳細", tone="soft")
