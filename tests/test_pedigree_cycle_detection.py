import pytest

from src.services.pedigree_service import build_graph


def test_build_graph_rejects_cycle() -> None:
    varieties = [{"id": "a", "name": "A"}, {"id": "b", "name": "B"}, {"id": "c", "name": "C"}]
    links = [
        {"parent_variety_id": "a", "child_variety_id": "b"},
        {"parent_variety_id": "b", "child_variety_id": "c"},
        {"parent_variety_id": "c", "child_variety_id": "a"},
    ]
    with pytest.raises(ValueError):
        build_graph(varieties, links)
