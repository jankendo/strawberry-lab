from types import SimpleNamespace

from src.services import variety_service


class _ChunkingTable:
    def __init__(self, name: str, client: "_ChunkingClient") -> None:
        self.name = name
        self.client = client
        self._filters: list[tuple[str, str, object]] = []
        self._orders: list[tuple[str, bool]] = []

    def select(self, *_args, **_kwargs):
        return self

    def in_(self, column: str, values: list[str]):
        values_copy = list(values)
        self._filters.append(("in", column, values_copy))
        self.client.in_calls.append((self.name, column, values_copy))
        return self

    def is_(self, column: str, value: object):
        self._filters.append(("is", column, value))
        return self

    def order(self, column: str, *, desc: bool = False):
        self._orders.append((column, bool(desc)))
        return self

    def execute(self):
        rows = [dict(row) for row in self.client.rows.get(self.name, [])]
        for mode, column, value in self._filters:
            if mode == "in":
                rows = [row for row in rows if row.get(column) in value]
            elif mode == "is":
                if value == "null":
                    rows = [row for row in rows if row.get(column) is None]
                else:
                    rows = [row for row in rows if row.get(column) is value]
        for column, desc in reversed(self._orders):
            rows.sort(key=lambda row: row.get(column), reverse=desc)
        return SimpleNamespace(data=rows, count=len(rows))


class _ChunkingClient:
    def __init__(self, rows: dict[str, list[dict]]) -> None:
        self.rows = rows
        self.in_calls: list[tuple[str, str, list[str]]] = []

    def table(self, name: str) -> _ChunkingTable:
        return _ChunkingTable(name, self)


def test_get_review_counts_for_varieties_chunks_large_id_lists(monkeypatch) -> None:
    review_rows = [{"variety_id": f"id-{index}", "deleted_at": None} for index in range(205)]
    client = _ChunkingClient({"reviews": review_rows})
    monkeypatch.setattr(variety_service, "get_user_client", lambda: client)
    variety_service.get_review_counts_for_varieties.clear()

    counts = variety_service.get_review_counts_for_varieties([f"id-{index}" for index in range(205)])

    assert len([call for call in client.in_calls if call[0] == "reviews"]) == 2
    assert counts["id-0"] == 1
    assert counts["id-204"] == 1


def test_get_latest_review_summary_for_varieties_chunks_large_id_lists(monkeypatch) -> None:
    review_rows = [
        {
            "variety_id": f"id-{index}",
            "tasted_date": "2026-04-07",
            "updated_at": "2026-04-07T00:00:00+00",
            "created_at": "2026-04-07T00:00:00+00",
            "deleted_at": None,
        }
        for index in range(205)
    ]
    client = _ChunkingClient({"reviews": review_rows})
    monkeypatch.setattr(variety_service, "get_user_client", lambda: client)
    variety_service.get_latest_review_summary_for_varieties.clear()

    latest = variety_service.get_latest_review_summary_for_varieties([f"id-{index}" for index in range(205)])

    assert len([call for call in client.in_calls if call[0] == "reviews"]) == 2
    assert latest["id-0"]["variety_id"] == "id-0"
    assert latest["id-204"]["variety_id"] == "id-204"
