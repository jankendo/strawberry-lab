from collections import defaultdict

from src.services.pedigree_service import build_figure, build_graph, layered_layout


def _dense_dag() -> tuple[list[dict], list[dict]]:
    varieties = [
        {"id": "r1", "name": "Root 1"},
        {"id": "r2", "name": "Root 2"},
        {"id": "m1", "name": "Mid 1"},
        {"id": "m2", "name": "Mid 2"},
        {"id": "m3", "name": "Mid 3"},
        {"id": "m4", "name": "Mid 4"},
        {"id": "l1", "name": "Leaf 1"},
        {"id": "l2", "name": "Leaf 2"},
        {"id": "l3", "name": "Leaf 3"},
    ]
    links = [
        {"parent_variety_id": "r1", "child_variety_id": "m1"},
        {"parent_variety_id": "r1", "child_variety_id": "m2"},
        {"parent_variety_id": "r1", "child_variety_id": "m3"},
        {"parent_variety_id": "r2", "child_variety_id": "m2"},
        {"parent_variety_id": "r2", "child_variety_id": "m3"},
        {"parent_variety_id": "r2", "child_variety_id": "m4"},
        {"parent_variety_id": "m1", "child_variety_id": "l1"},
        {"parent_variety_id": "m2", "child_variety_id": "l1"},
        {"parent_variety_id": "m2", "child_variety_id": "l2"},
        {"parent_variety_id": "m3", "child_variety_id": "l2"},
        {"parent_variety_id": "m3", "child_variety_id": "l3"},
        {"parent_variety_id": "m4", "child_variety_id": "l3"},
    ]
    return varieties, links


def test_layered_layout_is_stable_and_respects_depth_order() -> None:
    varieties, links = _dense_dag()
    graph = build_graph(varieties, links)

    first_layout = layered_layout(graph)
    second_layout = layered_layout(graph)

    assert first_layout == second_layout
    for parent, child in graph.edges():
        assert first_layout[child][1] < first_layout[parent][1]


def test_layered_layout_keeps_minimum_horizontal_separation_per_layer() -> None:
    varieties, links = _dense_dag()
    graph = build_graph(varieties, links)
    positions = layered_layout(graph)

    xs_by_layer: defaultdict[float, list[float]] = defaultdict(list)
    for node in graph.nodes():
        x, y = positions[node]
        xs_by_layer[round(y, 6)].append(x)

    for layer_positions in xs_by_layer.values():
        if len(layer_positions) < 2:
            continue
        ordered = sorted(layer_positions)
        gaps = [ordered[idx + 1] - ordered[idx] for idx in range(len(ordered) - 1)]
        assert min(gaps) >= 2.0


def test_build_figure_sets_readable_viewport_defaults() -> None:
    varieties, links = _dense_dag()
    graph = build_graph(varieties, links)
    positions = layered_layout(graph)

    figure = build_figure(graph, positions, review_stats={})

    assert figure.layout.height >= 620
    assert figure.layout.xaxis.range is not None
    assert figure.layout.yaxis.range is not None
    assert figure.layout.xaxis.range[0] < figure.layout.xaxis.range[1]
    assert figure.layout.yaxis.range[0] < figure.layout.yaxis.range[1]
