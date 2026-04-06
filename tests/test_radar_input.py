from src.components.radar_input import (
    _DEFAULT_AXIS_KEYS,
    _normalize_axis_keys,
    _normalize_component_scores,
    _normalize_scale,
    _normalize_scores,
)


def test_normalize_axis_keys_falls_back_when_input_is_not_five_unique_keys() -> None:
    assert _normalize_axis_keys(["a", "b", "c", "d"]) == _DEFAULT_AXIS_KEYS
    assert _normalize_axis_keys(["a", "b", "c", "d", "d"]) == _DEFAULT_AXIS_KEYS


def test_normalize_scale_sorts_range_and_snaps_default_to_step() -> None:
    normalized = _normalize_scale(min_value=8, max_value=2, step=4, default_value=7)
    assert normalized == (2, 8, 4, 6)


def test_normalize_scores_clamps_invalid_and_missing_values() -> None:
    scores = _normalize_scores(
        {
            "sweetness": "99",
            "sourness": "invalid",
            "aroma": 2.2,
            "texture": 0,
            "appearance": None,
        },
        axis_keys=_DEFAULT_AXIS_KEYS,
        min_value=1,
        max_value=5,
        step=1,
        default_value=3,
    )
    assert scores == {
        "sweetness": 5,
        "sourness": 3,
        "aroma": 2,
        "texture": 1,
        "appearance": 3,
    }


def test_normalize_component_scores_accepts_nested_scores_payload() -> None:
    scores = _normalize_component_scores(
        {
            "scores": {
                "sweetness": 1,
                "sourness": 2,
                "aroma": 3,
                "texture": 4,
                "appearance": 5,
                "ignored": 10,
            }
        },
        axis_keys=_DEFAULT_AXIS_KEYS,
        min_value=1,
        max_value=5,
        step=1,
        default_value=3,
    )
    assert scores == {
        "sweetness": 1,
        "sourness": 2,
        "aroma": 3,
        "texture": 4,
        "appearance": 5,
    }


def test_normalize_component_scores_returns_none_for_non_mapping_payload() -> None:
    scores = _normalize_component_scores(
        payload="invalid-payload",
        axis_keys=_DEFAULT_AXIS_KEYS,
        min_value=1,
        max_value=5,
        step=1,
        default_value=3,
    )
    assert scores is None
