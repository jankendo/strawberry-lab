"""Pedigree graph generation service."""

from __future__ import annotations

from collections import defaultdict, deque

import networkx as nx
import plotly.graph_objects as go


def fetch_graph_data(include_deleted: bool = False) -> tuple[list[dict], list[dict]]:
    """Fetch varieties and parent links for graph build."""
    from src.services.auth_service import get_user_client

    client = get_user_client()
    vquery = client.table("varieties").select("id,name,deleted_at")
    if not include_deleted:
        vquery = vquery.is_("deleted_at", "null")
    varieties = vquery.execute().data or []
    links = client.table("variety_parent_links").select("*").execute().data or []
    return varieties, links


def build_graph(varieties: list[dict], links: list[dict]) -> nx.DiGraph:
    """Build directed pedigree graph and enforce DAG."""
    graph = nx.DiGraph()
    for variety in varieties:
        graph.add_node(variety["id"], name=variety["name"])
    for link in links:
        if link["parent_variety_id"] in graph and link["child_variety_id"] in graph:
            graph.add_edge(link["parent_variety_id"], link["child_variety_id"], crossed_year=link.get("crossed_year"))
    if not nx.is_directed_acyclic_graph(graph):
        raise ValueError("循環が検出されました。")
    return graph


def subgraph_by_root(graph: nx.DiGraph, root_id: str, direction: str, max_depth: int) -> nx.DiGraph:
    """Return root-focused subgraph by direction and depth."""
    if not root_id or root_id not in graph:
        return graph
    visited: set[str] = {root_id}
    queue: deque[tuple[str, int]] = deque([(root_id, 0)])
    while queue:
        node, depth = queue.popleft()
        if depth >= max_depth:
            continue
        neighbors = []
        if direction in ("descendants", "both"):
            neighbors.extend(graph.successors(node))
        if direction in ("ancestors", "both"):
            neighbors.extend(graph.predecessors(node))
        for nxt in neighbors:
            if nxt in visited:
                continue
            visited.add(nxt)
            queue.append((nxt, depth + 1))
    return graph.subgraph(visited).copy()


def layered_layout(graph: nx.DiGraph) -> dict[str, tuple[float, float]]:
    """Compute pure-Python top-down layered layout."""
    in_degree = dict(graph.in_degree())
    roots = [n for n, degree in in_degree.items() if degree == 0] or list(graph.nodes)
    level: dict[str, int] = {}
    queue: deque[tuple[str, int]] = deque((root, 0) for root in roots)
    while queue:
        node, depth = queue.popleft()
        if node in level and level[node] <= depth:
            continue
        level[node] = depth
        for child in graph.successors(node):
            queue.append((child, depth + 1))
    by_level: defaultdict[int, list[str]] = defaultdict(list)
    for node in graph.nodes:
        by_level[level.get(node, 0)].append(node)
    pos: dict[str, tuple[float, float]] = {}
    for depth, nodes in sorted(by_level.items()):
        count = len(nodes)
        for idx, node in enumerate(sorted(nodes, key=str)):
            x = idx - (count - 1) / 2
            y = -depth
            pos[node] = (x, y)
    return pos


def build_figure(graph: nx.DiGraph, positions: dict[str, tuple[float, float]], review_stats: dict[str, dict]) -> go.Figure:
    """Build clickable plotly figure for pedigree graph."""
    edge_x: list[float] = []
    edge_y: list[float] = []
    for source, target in graph.edges():
        x0, y0 = positions[source]
        x1, y1 = positions[target]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])
    edge_trace = go.Scatter(x=edge_x, y=edge_y, mode="lines", line={"width": 1}, hoverinfo="none")
    node_x, node_y, node_text, node_ids, node_color, node_size = [], [], [], [], [], []
    for node in graph.nodes():
        x, y = positions[node]
        stats = review_stats.get(node, {"avg_overall": None, "review_count": 0})
        avg = stats.get("avg_overall")
        if avg is None:
            color = "#BFBFBF"
        elif avg < 4:
            color = "#F9D5D8"
        elif avg < 7:
            color = "#EE8894"
        else:
            color = "#B7132C"
        node_x.append(x)
        node_y.append(y)
        node_text.append(graph.nodes[node].get("name", node))
        node_ids.append(node)
        node_color.append(color)
        node_size.append(14 + min(int(stats.get("review_count", 0)), 20))
    node_trace = go.Scatter(
        x=node_x,
        y=node_y,
        mode="markers+text",
        text=node_text,
        textposition="top center",
        marker={"size": node_size, "color": node_color, "line": {"width": 1, "color": "#333"}},
        customdata=node_ids,
        hovertemplate="%{text}<extra></extra>",
    )
    return go.Figure(data=[edge_trace, node_trace]).update_layout(showlegend=False, xaxis={"visible": False}, yaxis={"visible": False}, margin={"l": 10, "r": 10, "t": 10, "b": 10})
