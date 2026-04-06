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

render_section_title("交配図の設定ガイド", "初めてでも設定できるように、入力手順を整理しています。")
with st.expander("交配図の作り方（詳しく見る）", expanded=False):
    st.markdown(
        """
        **1. まず親品種リンクを登録する（品種管理ページ）**  
        1. 「品種管理」→「作成・編集」で対象品種を選びます。  
        2. 「親品種」マルチセレクトで親を追加します。  
        3. 保存すると、交配図ページに系統が反映されます。  

        **2. 交配図ページで表示条件を調整する**  
        - **起点品種**: 中心にしたい品種を選択  
        - **表示方向**: 祖先 / 子孫 / 両方  
        - **最大深さ**: 何世代まで表示するか  

        **3. ノードをクリックして詳細確認**  
        グラフ上のノードをクリックすると、品種管理ページへ遷移して詳細を確認できます。  

        **4. よくあるつまずき**  
        - `交配リンクで循環が発生します`  
          - 親子関係がループしている状態です。親品種設定を見直してください。  
        - グラフが小さい / 見切れる  
          - 起点品種を指定し、最大深さを 2〜3 に下げると見やすくなります。  
        - 何も表示されない  
          - 親品種リンク未登録の可能性があります。まず品種管理で親を設定してください。  
        """
    )

render_section_title("表示条件")
c1, c2, c3 = st.columns(3)
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
