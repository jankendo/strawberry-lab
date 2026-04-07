from datetime import date, timedelta

import pytest

from src.utils.validation import validate_review_payload, validate_variety_payload


def _review_payload(tasted_date) -> dict:
    return {
        "variety_id": "v",
        "tasted_date": tasted_date,
        "sweetness": 3,
        "sourness": 3,
        "aroma": 3,
        "texture": 3,
        "appearance": 3,
        "overall": 6,
    }


def test_validate_variety_payload_rejects_invalid_brix_range() -> None:
    payload = {"name": "Test", "brix_min": 20, "brix_max": 10}
    with pytest.raises(ValueError):
        validate_variety_payload(payload)


def test_validate_review_payload_rejects_future_date() -> None:
    payload = _review_payload(date.today() + timedelta(days=1))
    with pytest.raises(ValueError):
        validate_review_payload(payload)


def test_validate_review_payload_rejects_future_date_string() -> None:
    payload = _review_payload((date.today() + timedelta(days=1)).isoformat())
    with pytest.raises(ValueError):
        validate_review_payload(payload)


@pytest.mark.parametrize(
    ("input_date", "expected"),
    [
        (date(2025, 1, 1), "2025-01-01"),
        ("2025-01-01", "2025-01-01"),
    ],
)
def test_validate_review_payload_normalizes_tasted_date(input_date, expected: str) -> None:
    payload = _review_payload(input_date)
    validated = validate_review_payload(payload)
    assert validated["tasted_date"] == expected
