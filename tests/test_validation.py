from datetime import date, timedelta

import pytest

from src.utils.validation import validate_note_payload, validate_review_payload, validate_variety_payload


def test_validate_variety_payload_rejects_invalid_brix_range() -> None:
    payload = {"name": "Test", "brix_min": 20, "brix_max": 10}
    with pytest.raises(ValueError):
        validate_variety_payload(payload)


def test_validate_review_payload_rejects_future_date() -> None:
    payload = {
        "variety_id": "v",
        "tasted_date": date.today() + timedelta(days=1),
        "sweetness": 3,
        "sourness": 3,
        "aroma": 3,
        "texture": 3,
        "appearance": 3,
        "overall": 6,
    }
    with pytest.raises(ValueError):
        validate_review_payload(payload)


def test_validate_note_payload_limits_title_length() -> None:
    payload = {"title": "x" * 201, "body": "body"}
    with pytest.raises(ValueError):
        validate_note_payload(payload)
