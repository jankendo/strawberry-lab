from src.utils.navigation import (
    build_review_variety_query_params,
    build_selected_variety_query_params,
    resolve_review_variety_query_param,
    resolve_selected_variety_query_param,
)


def test_build_review_variety_query_params_returns_single_value_mapping() -> None:
    assert build_review_variety_query_params(" variety-1 ") == {"review_variety_id": "variety-1"}


def test_build_selected_variety_query_params_skips_blank_values() -> None:
    assert build_selected_variety_query_params("   ") == {}


def test_resolve_review_variety_query_param_reads_first_sequence_value() -> None:
    assert resolve_review_variety_query_param({"review_variety_id": [" review-1 ", "review-2"]}) == "review-1"


def test_resolve_selected_variety_query_param_strips_scalar_values() -> None:
    assert resolve_selected_variety_query_param({"selected_variety_id": " variety-7 "}) == "variety-7"
