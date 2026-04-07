from src.components.sidebar import _resolve_mobile_active_tab


def test_resolve_mobile_active_tab_returns_core_tab_for_core_pages() -> None:
    assert _resolve_mobile_active_tab("dashboard") == "dashboard"
    assert _resolve_mobile_active_tab("reviews") == "reviews"


def test_resolve_mobile_active_tab_maps_more_group_pages() -> None:
    assert _resolve_mobile_active_tab("pedigree") == "more"
    assert _resolve_mobile_active_tab("settings") == "more"
    assert _resolve_mobile_active_tab("unknown") == "more"
