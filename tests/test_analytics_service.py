from datetime import date
from types import SimpleNamespace

from src.services import analytics_service


class _AnalyticsTable:
    def __init__(self, name: str, client: "_AnalyticsClient") -> None:
        self.name = name
        self.client = client
        self._in_filters: list[tuple[str, list[str]]] = []
        self._null_filters: list[str] = []
        self._gte_filters: list[tuple[str, str]] = []
        self._lte_filters: list[tuple[str, str]] = []

    def select(self, *_args, **_kwargs):
        return self

    def in_(self, column: str, values: list[str]):
        values_copy = list(values)
        self._in_filters.append((column, values_copy))
        self.client.in_calls.append((self.name, column, values_copy))
        return self

    def is_(self, column: str, value: object):
        if value == "null":
            self._null_filters.append(column)
        return self

    def gte(self, column: str, value: str):
        self._gte_filters.append((column, value))
        return self

    def lte(self, column: str, value: str):
        self._lte_filters.append((column, value))
        return self

    def eq(self, _column: str, _value: str):
        return self

    def contains(self, _column: str, _value: list[str]):
        return self

    def execute(self):
        rows = [dict(row) for row in self.client.rows.get(self.name, [])]
        for column in self._null_filters:
            rows = [row for row in rows if row.get(column) is None]
        for column, values in self._in_filters:
            rows = [row for row in rows if row.get(column) in values]
        for column, value in self._gte_filters:
            rows = [row for row in rows if str(row.get(column) or "") >= value]
        for column, value in self._lte_filters:
            rows = [row for row in rows if str(row.get(column) or "") <= value]
        return SimpleNamespace(data=rows, count=len(rows))


class _AnalyticsClient:
    def __init__(self, rows: dict[str, list[dict]]) -> None:
        self.rows = rows
        self.in_calls: list[tuple[str, str, list[str]]] = []

    def table(self, name: str) -> _AnalyticsTable:
        return _AnalyticsTable(name, self)


def test_get_filtered_review_dataframe_chunks_large_variety_id_lists(monkeypatch) -> None:
    review_rows = [
        {
            "id": f"review-{index}",
            "variety_id": f"variety-{index}",
            "tasted_date": "2026-04-07",
            "overall": 8,
            "sweetness": 4,
            "sourness": 3,
            "aroma": 4,
            "texture": 4,
            "appearance": 4,
            "deleted_at": None,
        }
        for index in range(205)
    ]
    variety_rows = [
        {
            "id": f"variety-{index}",
            "name": f"品種{index}",
            "origin_prefecture": None,
            "tags": [],
            "brix_min": None,
            "brix_max": None,
            "deleted_at": None,
        }
        for index in range(205)
    ]
    client = _AnalyticsClient({"reviews": review_rows, "varieties": variety_rows})
    monkeypatch.setattr(analytics_service, "get_user_client", lambda: client)
    analytics_service.get_filtered_review_dataframe.clear()

    df = analytics_service.get_filtered_review_dataframe(
        date_from=date(2026, 4, 1),
        date_to=date(2026, 4, 30),
        variety_ids=[f"variety-{index}" for index in range(205)],
    )

    review_in_calls = [call for call in client.in_calls if call[0] == "reviews"]
    variety_in_calls = [call for call in client.in_calls if call[0] == "varieties"]
    assert len(review_in_calls) == 2
    assert len(variety_in_calls) == 2
    assert len(df) == 205
