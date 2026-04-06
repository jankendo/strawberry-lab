from datetime import date

import pytest

from src.services import review_service


class _CacheClear:
    def __init__(self) -> None:
        self.called = False

    def clear(self) -> None:
        self.called = True


class _DuplicateLookupQuery:
    def select(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def is_(self, *_args, **_kwargs):
        return self

    def maybe_single(self):
        return self

    def execute(self):
        return None


class _InsertQuery:
    def __init__(self) -> None:
        self.inserted_payload: dict | None = None

    def insert(self, payload: dict):
        self.inserted_payload = payload.copy()
        return self

    def execute(self):
        return None


class _UpdateQuery:
    def __init__(self) -> None:
        self.updated_payload: dict | None = None
        self.eq_calls: list[tuple[str, str]] = []

    def update(self, payload: dict):
        self.updated_payload = payload.copy()
        return self

    def eq(self, key: str, value: str):
        self.eq_calls.append((key, value))
        return self

    def execute(self):
        return None


class _Client:
    def __init__(self, query) -> None:
        self.query = query

    def table(self, name: str):
        assert name == "reviews"
        return self.query


def _sample_payload() -> dict:
    return {
        "variety_id": "variety-1",
        "tasted_date": date(2025, 1, 1),
        "sweetness": 3,
        "sourness": 3,
        "aroma": 3,
        "texture": 3,
        "appearance": 3,
        "overall": 7,
    }


def _install_cache_spies(monkeypatch):
    list_cache = _CacheClear()
    pokedex_cache = _CacheClear()
    count_cache = _CacheClear()
    monkeypatch.setattr(review_service, "list_reviews", list_cache)
    monkeypatch.setattr(review_service, "get_pokedex_progress", pokedex_cache)
    monkeypatch.setattr(review_service, "get_review_counts_for_varieties", count_cache)
    return list_cache, pokedex_cache, count_cache


def test_find_duplicate_returns_none_when_execute_response_is_none(monkeypatch) -> None:
    monkeypatch.setattr(review_service, "get_user_client", lambda: _Client(_DuplicateLookupQuery()))
    assert review_service._find_duplicate("variety-1", "2025-01-01") is None


def test_create_or_update_review_raises_duplicate_without_overwrite(monkeypatch) -> None:
    monkeypatch.setattr(review_service, "get_user_client", lambda: object())
    monkeypatch.setattr(review_service, "validate_review_payload", lambda payload: payload.copy())
    monkeypatch.setattr(review_service, "_find_duplicate", lambda *_args, **_kwargs: {"id": "dup-id"})
    with pytest.raises(ValueError, match="DUPLICATE_REVIEW"):
        review_service.create_or_update_review(_sample_payload())


def test_create_review_uses_generated_id_when_insert_response_has_no_data(monkeypatch) -> None:
    insert_query = _InsertQuery()
    monkeypatch.setattr(review_service, "get_user_client", lambda: _Client(insert_query))
    monkeypatch.setattr(review_service, "validate_review_payload", lambda payload: payload.copy())
    monkeypatch.setattr(review_service, "_find_duplicate", lambda *_args, **_kwargs: None)
    list_cache, pokedex_cache, count_cache = _install_cache_spies(monkeypatch)

    review_id, overwritten = review_service.create_or_update_review(_sample_payload())

    assert overwritten is False
    assert insert_query.inserted_payload is not None
    assert insert_query.inserted_payload["id"] == review_id
    assert list_cache.called and pokedex_cache.called and count_cache.called


def test_create_or_update_review_overwrites_duplicate(monkeypatch) -> None:
    update_query = _UpdateQuery()
    monkeypatch.setattr(review_service, "get_user_client", lambda: _Client(update_query))
    monkeypatch.setattr(review_service, "validate_review_payload", lambda payload: payload.copy())
    monkeypatch.setattr(review_service, "_find_duplicate", lambda *_args, **_kwargs: {"id": "dup-id"})
    list_cache, pokedex_cache, count_cache = _install_cache_spies(monkeypatch)

    review_id, overwritten = review_service.create_or_update_review(_sample_payload(), overwrite_duplicate=True)

    assert review_id == "dup-id"
    assert overwritten is True
    assert update_query.updated_payload is not None
    assert ("id", "dup-id") in update_query.eq_calls
    assert list_cache.called and pokedex_cache.called and count_cache.called


def test_create_review_normalizes_tasted_date_before_insert(monkeypatch) -> None:
    insert_query = _InsertQuery()
    observed: dict[str, str] = {}

    def _find_duplicate(_variety_id: str, tasted_date: str):
        observed["tasted_date"] = tasted_date
        return None

    monkeypatch.setattr(review_service, "get_user_client", lambda: _Client(insert_query))
    monkeypatch.setattr(review_service, "_find_duplicate", _find_duplicate)
    _install_cache_spies(monkeypatch)
    payload = _sample_payload()

    review_service.create_or_update_review(payload)

    assert observed["tasted_date"] == "2025-01-01"
    assert insert_query.inserted_payload is not None
    assert insert_query.inserted_payload["tasted_date"] == "2025-01-01"


def test_create_review_duplicate_error_still_normalizes_input_payload(monkeypatch) -> None:
    observed: dict[str, str] = {}

    def _find_duplicate(_variety_id: str, tasted_date: str):
        observed["tasted_date"] = tasted_date
        return {"id": "dup-id"}

    monkeypatch.setattr(review_service, "get_user_client", lambda: object())
    monkeypatch.setattr(review_service, "_find_duplicate", _find_duplicate)
    payload = _sample_payload()

    with pytest.raises(ValueError, match="DUPLICATE_REVIEW"):
        review_service.create_or_update_review(payload)

    assert observed["tasted_date"] == "2025-01-01"
    assert payload["tasted_date"] == "2025-01-01"
