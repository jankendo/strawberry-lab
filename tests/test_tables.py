from src.components.tables import _format_cell_value


def test_format_cell_value_handles_relation_dict() -> None:
    assert _format_cell_value("varieties", {"name": "とちおとめ"}) == "とちおとめ"


def test_format_cell_value_handles_relation_list() -> None:
    value = [{"name": "とちあいか"}, {"name": "あまおう"}]
    assert _format_cell_value("varieties", value) == "とちあいか | あまおう"


def test_format_cell_value_handles_empty_unhashable_values() -> None:
    assert _format_cell_value("varieties", {}) == "-"
    assert _format_cell_value("varieties", []) == "-"


def test_format_cell_value_preserves_existing_formatting() -> None:
    assert _format_cell_value("tasted_date", "2025-01-20T08:30:00") == "2025-01-20"
    assert _format_cell_value("status", "running") == "⏳ running"
    assert _format_cell_value("status", {"name": "running"}) == "⏳ running"
    assert _format_cell_value("detail_url", {"href": "https://example.com"}) == "🔗 リンク"
