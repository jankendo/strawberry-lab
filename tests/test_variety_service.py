from types import SimpleNamespace

from src.services import variety_service


class _ChunkingTable:
    def __init__(self, name: str, client: "_ChunkingClient") -> None:
        self.name = name
        self.client = client
        self._filters: list[tuple[str, str, object]] = []
        self._orders: list[tuple[str, bool]] = []
        self._range: tuple[int, int] | None = None

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

    def range(self, start: int, end: int):
        self._range = (int(start), int(end))
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
        if self._range is not None:
            start, end = self._range
            rows = rows[start : end + 1]
        return SimpleNamespace(data=rows, count=len(rows))


class _ChunkingClient:
    def __init__(self, rows: dict[str, list[dict]]) -> None:
        self.rows = rows
        self.in_calls: list[tuple[str, str, list[str]]] = []

    def table(self, name: str) -> _ChunkingTable:
        return _ChunkingTable(name, self)


class _RepeatingRangeTable(_ChunkingTable):
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
        if self._range is not None:
            _start, end = self._range
            rows = rows[: end + 1]
        return SimpleNamespace(data=rows, count=len(rows))


class _RepeatingRangeClient(_ChunkingClient):
    def table(self, name: str) -> _ChunkingTable:
        return _RepeatingRangeTable(name, self)


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


def test_list_varieties_for_list_tab_matches_hiragana_keyword_to_katakana_name(monkeypatch) -> None:
    client = _ChunkingClient(
        {
            "varieties": [
                {
                    "id": "id-1",
                    "name": "サガホノカ",
                    "alias_names": [],
                    "japanese_name": None,
                    "origin_prefecture": "佐賀県",
                    "registration_number": "111",
                    "application_number": "A-1",
                    "description": "甘い品種",
                    "characteristics_summary": "香りが良い",
                    "developer": "佐賀",
                    "updated_at": "2026-04-07T00:00:00+00",
                    "created_at": "2026-04-06T00:00:00+00",
                    "registered_year": 2026,
                    "registration_date": "2026-04-01",
                    "deleted_at": None,
                },
                {
                    "id": "id-2",
                    "name": "ベニホッペ",
                    "alias_names": [],
                    "japanese_name": None,
                    "origin_prefecture": "静岡県",
                    "registration_number": "222",
                    "application_number": "A-2",
                    "description": "酸味あり",
                    "characteristics_summary": "果肉がしっかり",
                    "developer": "静岡",
                    "updated_at": "2026-04-06T00:00:00+00",
                    "created_at": "2026-04-05T00:00:00+00",
                    "registered_year": 2025,
                    "registration_date": "2025-04-01",
                    "deleted_at": None,
                },
            ]
        }
    )
    monkeypatch.setattr(variety_service, "get_user_client", lambda: client)
    monkeypatch.setattr(variety_service, "get_discovered_variety_ids", lambda: [])
    variety_service.list_variety_list_index.clear()

    rows, total, selected_matches = variety_service.list_varieties_for_list_tab(keyword="さが", selected_id="id-1")

    assert total == 1
    assert [row["id"] for row in rows] == ["id-1"]
    assert selected_matches is True


def test_list_varieties_for_list_tab_filters_discovered_rows_before_paging(monkeypatch) -> None:
    client = _ChunkingClient(
        {
            "varieties": [
                {
                    "id": f"id-{index}",
                    "name": f"品種{index}",
                    "alias_names": [],
                    "japanese_name": None,
                    "origin_prefecture": "佐賀県",
                    "registration_number": str(index),
                    "application_number": f"A-{index}",
                    "description": "",
                    "characteristics_summary": "",
                    "developer": "",
                    "updated_at": f"2026-04-{(index % 9) + 1:02d}T00:00:00+00",
                    "created_at": f"2026-03-{(index % 9) + 1:02d}T00:00:00+00",
                    "registered_year": 2026,
                    "registration_date": f"2026-04-{(index % 9) + 1:02d}",
                    "deleted_at": None,
                }
                for index in range(6)
            ]
        }
    )
    monkeypatch.setattr(variety_service, "get_user_client", lambda: client)
    monkeypatch.setattr(variety_service, "get_discovered_variety_ids", lambda: ["id-1", "id-3", "id-5"])
    variety_service.list_variety_list_index.clear()

    rows, total, selected_matches = variety_service.list_varieties_for_list_tab(
        discovery_filter="発見済み",
        sort_field="name",
        sort_desc=False,
        page=1,
        page_size=2,
        selected_id="id-5",
    )

    assert total == 3
    assert [row["id"] for row in rows] == ["id-1", "id-3"]
    assert selected_matches is True


def test_list_varieties_for_list_tab_uses_discovered_only_index(monkeypatch) -> None:
    monkeypatch.setattr(variety_service, "_DISCOVERED_DIRECT_QUERY_LIMIT", 0)
    monkeypatch.setattr(variety_service, "get_discovered_variety_ids", lambda: ["id-3", "id-5"])
    monkeypatch.setattr(
        variety_service,
        "list_variety_sort_index_for_ids",
        lambda ids: [
            {
                "id": "id-3",
                "name": "サガホノカ",
                "origin_prefecture": "佐賀県",
                "updated_at": "2026-04-01",
                "created_at": "2026-04-01",
                "registered_year": 2026,
                "registration_date": "2026-04-01",
            },
            {
                "id": "id-5",
                "name": "ベニホッペ",
                "origin_prefecture": "静岡県",
                "updated_at": "2026-04-01",
                "created_at": "2026-04-01",
                "registered_year": 2026,
                "registration_date": "2026-04-01",
            },
        ]
        if list(ids) == ["id-3", "id-5"]
        else [],
    )
    monkeypatch.setattr(
        variety_service,
        "list_variety_list_index_for_ids",
        lambda ids: [
            {
                "id": "id-3",
                "name": "サガホノカ",
                "alias_names": [],
                "_search_key": "サガホノカ",
                "origin_prefecture": "佐賀県",
                "updated_at": "2026-04-01",
                "created_at": "2026-04-01",
                "registered_year": 2026,
                "registration_date": "2026-04-01",
            },
            {
                "id": "id-5",
                "name": "ベニホッペ",
                "alias_names": [],
                "_search_key": "ベニホッペ",
                "origin_prefecture": "静岡県",
                "updated_at": "2026-04-01",
                "created_at": "2026-04-01",
                "registered_year": 2026,
                "registration_date": "2026-04-01",
            },
        ]
        if list(ids) == ["id-3", "id-5"]
        else [],
    )

    def _unexpected_full_index():
        raise AssertionError("full variety index should not be loaded for 発見済み filter")

    monkeypatch.setattr(variety_service, "list_variety_list_index", _unexpected_full_index)
    monkeypatch.setattr(variety_service, "list_variety_sort_index", _unexpected_full_index)

    rows, total, selected_matches = variety_service.list_varieties_for_list_tab(
        discovery_filter="発見済み",
        sort_field="name",
        sort_desc=False,
        selected_id="id-5",
    )

    assert total == 2
    assert [row["id"] for row in rows] == ["id-3", "id-5"]
    assert selected_matches is True


def test_get_variety_list_page_ids_uses_direct_page_query_for_default_view(monkeypatch) -> None:
    monkeypatch.setattr(
        variety_service,
        "list_varieties",
        lambda **kwargs: ([{"id": "id-2"}, {"id": "id-4"}], 2),
    )
    monkeypatch.setattr(
        variety_service,
        "list_variety_sort_index_for_ids",
        lambda ids: [{"id": "id-4"}] if list(ids) == ["id-4"] else [],
    )

    def _unexpected_search_index():
        raise AssertionError("search indexes should not be loaded for default no-keyword view")

    monkeypatch.setattr(variety_service, "list_variety_list_index", _unexpected_search_index)
    monkeypatch.setattr(variety_service, "list_variety_sort_index", _unexpected_search_index)

    page_ids, total, selected_matches = variety_service.get_variety_list_page_ids(selected_id="id-4")

    assert page_ids == ["id-2", "id-4"]
    assert total == 2
    assert selected_matches is True


def test_get_variety_list_page_ids_uses_direct_page_query_for_discovered_default_view(monkeypatch) -> None:
    client = _ChunkingClient(
        {
            "varieties": [
                {
                    "id": "id-2",
                    "name": "品種2",
                    "origin_prefecture": "佐賀県",
                    "updated_at": "2026-04-03",
                    "created_at": "2026-04-03",
                    "registered_year": 2026,
                    "registration_date": "2026-04-03",
                    "deleted_at": None,
                },
                {
                    "id": "id-4",
                    "name": "品種4",
                    "origin_prefecture": "佐賀県",
                    "updated_at": "2026-04-01",
                    "created_at": "2026-04-01",
                    "registered_year": 2026,
                    "registration_date": "2026-04-01",
                    "deleted_at": None,
                },
            ]
        }
    )
    monkeypatch.setattr(variety_service, "get_user_client", lambda: client)
    monkeypatch.setattr(variety_service, "get_discovered_variety_ids", lambda: ["id-2", "id-4"])

    def _unexpected_index():
        raise AssertionError("discovered default view should not build a full sort/search index")

    monkeypatch.setattr(variety_service, "list_variety_sort_index_for_ids", _unexpected_index)
    monkeypatch.setattr(variety_service, "list_variety_list_index_for_ids", _unexpected_index)

    page_ids, total, selected_matches = variety_service.get_variety_list_page_ids(
        discovery_filter="発見済み",
        selected_id="id-4",
    )

    assert page_ids == ["id-2", "id-4"]
    assert total == 2
    assert selected_matches is True


def test_get_variety_list_rows_uses_minimal_payload_for_lightweight_ids(monkeypatch) -> None:
    monkeypatch.setattr(
        variety_service,
        "list_variety_list_index_for_ids",
        lambda ids: [{"id": "id-1", "name": "サガホノカ", "origin_prefecture": "佐賀県"}] if list(ids) == ["id-1"] else [],
    )
    monkeypatch.setattr(
        variety_service,
        "list_variety_locked_index_for_ids",
        lambda ids: [{"id": "id-2", "registration_number": "222", "application_number": "A-2"}] if list(ids) == ["id-2"] else [],
    )

    rows = variety_service.get_variety_list_rows(["id-1", "id-2"], lightweight_ids=["id-2"])

    assert rows == [
        {"id": "id-1", "name": "サガホノカ", "origin_prefecture": "佐賀県"},
        {"id": "id-2", "registration_number": "222", "application_number": "A-2"},
    ]


def test_list_variety_list_index_breaks_when_range_does_not_advance(monkeypatch) -> None:
    variety_rows = [
        {
            "id": f"id-{index:04d}",
            "name": f"品種{index}",
            "alias_names": [],
            "japanese_name": None,
            "origin_prefecture": "佐賀県",
            "registration_number": str(index),
            "application_number": f"A-{index}",
            "description": "",
            "characteristics_summary": "",
            "developer": "",
            "updated_at": "2026-04-01",
            "created_at": "2026-04-01",
            "registered_year": 2026,
            "registration_date": "2026-04-01",
            "deleted_at": None,
        }
        for index in range(1000)
    ]
    client = _RepeatingRangeClient({"varieties": variety_rows})
    monkeypatch.setattr(variety_service, "get_user_client", lambda: client)
    variety_service.list_variety_list_index.clear()

    rows = variety_service.list_variety_list_index()

    assert len(rows) == 1000
