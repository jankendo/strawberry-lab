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


def _spread_layer_positions(
    nodes: list[str],
    target_positions: dict[str, float],
    min_separation: float,
) -> dict[str, float]:
    """Place nodes in one layer with stable ordering and minimum spacing."""
    ordered_nodes = sorted(nodes, key=lambda node: (target_positions[node], str(node)))
    laid_out: dict[str, float] = {}
    for index, node in enumerate(ordered_nodes):
        position = target_positions[node]
        if index > 0:
            previous_node = ordered_nodes[index - 1]
            position = max(position, laid_out[previous_node] + min_separation)
        laid_out[node] = position
    if not ordered_nodes:
        return laid_out
    target_center = sum(target_positions[node] for node in ordered_nodes) / len(ordered_nodes)
    current_center = (laid_out[ordered_nodes[0]] + laid_out[ordered_nodes[-1]]) / 2
    center_shift = target_center - current_center
    return {node: position + center_shift for node, position in laid_out.items()}


def layered_layout(graph: nx.DiGraph) -> dict[str, tuple[float, float]]:
    """Compute deterministic layered layout with adaptive spacing for dense DAGs."""
    if graph.number_of_nodes() == 0:
        return {}

    topological_order = list(nx.lexicographical_topological_sort(graph, key=str))
    depth_by_node: dict[str, int] = {}
    for node in topological_order:
        parent_depths = [depth_by_node[parent] for parent in graph.predecessors(node)]
        depth_by_node[node] = (max(parent_depths) + 1) if parent_depths else 0

    nodes_by_depth: defaultdict[int, list[str]] = defaultdict(list)
    for node in topological_order:
        nodes_by_depth[depth_by_node[node]].append(node)

    def _layer_spacing(node_count: int) -> float:
        return 2.2 + min(1.0, node_count * 0.04)

    x_by_node: dict[str, float] = {}
    sorted_depths = sorted(nodes_by_depth)
    for depth in sorted_depths:
        layer_nodes = nodes_by_depth[depth]
        spacing = _layer_spacing(len(layer_nodes))
        start_x = -((len(layer_nodes) - 1) * spacing) / 2
        for index, node in enumerate(layer_nodes):
            x_by_node[node] = start_x + index * spacing

    for _ in range(2):
        for depth in sorted_depths[1:]:
            layer_nodes = nodes_by_depth[depth]
            spacing = _layer_spacing(len(layer_nodes))
            target_positions: dict[str, float] = {}
            for node in layer_nodes:
                parent_positions = [x_by_node[parent] for parent in graph.predecessors(node) if parent in x_by_node]
                if parent_positions:
                    target_positions[node] = sum(parent_positions) / len(parent_positions)
                else:
                    target_positions[node] = x_by_node[node]
            x_by_node.update(_spread_layer_positions(layer_nodes, target_positions, spacing))
        for depth in reversed(sorted_depths[:-1]):
            layer_nodes = nodes_by_depth[depth]
            spacing = _layer_spacing(len(layer_nodes))
            target_positions = {}
            for node in layer_nodes:
                child_positions = [x_by_node[child] for child in graph.successors(node) if child in x_by_node]
                if child_positions:
                    target_positions[node] = sum(child_positions) / len(child_positions)
                else:
                    target_positions[node] = x_by_node[node]
            x_by_node.update(_spread_layer_positions(layer_nodes, target_positions, spacing))

    max_layer_size = max(len(nodes) for nodes in nodes_by_depth.values())
    vertical_spacing = 2.4 + min(1.2, max_layer_size * 0.03)
    return {
        node: (x_by_node[node], -depth_by_node[node] * vertical_spacing)
        for node in topological_order
    }


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
    if node_x:
        min_x, max_x = min(node_x), max(node_x)
        min_y, max_y = min(node_y), max(node_y)
    else:
        min_x, max_x = -1.0, 1.0
        min_y, max_y = -1.0, 1.0
    x_span = max(max_x - min_x, 1.0)
    y_span = max(max_y - min_y, 1.0)
    x_padding = max(2.5, x_span * 0.12)
    y_padding = max(1.8, y_span * 0.25)
    height = int(max(620, min(1400, 460 + y_span * 80)))
    return go.Figure(data=[edge_trace, node_trace]).update_layout(
        showlegend=False,
        hovermode="closest",
        dragmode="pan",
        height=height,
        xaxis={"visible": False, "range": [min_x - x_padding, max_x + x_padding], "fixedrange": False},
        yaxis={"visible": False, "range": [min_y - y_padding, max_y + y_padding], "fixedrange": False},
        margin={"l": 30, "r": 30, "t": 30, "b": 30},
    )
