from scraper.import_pedigree_links import _filter_valid_rows


def test_filter_valid_rows_collects_missing_ids() -> None:
    rows = [
        {"child_variety_id": "child-a", "parent_variety_id": "parent-a", "parent_order": 1},
        {"child_variety_id": "child-b", "parent_variety_id": "parent-b", "parent_order": 2},
        {"child_variety_id": "child-a", "parent_variety_id": "parent-c", "parent_order": 2},
    ]

    valid_rows, missing_ids = _filter_valid_rows(rows, {"child-a", "parent-a"})

    assert valid_rows == [{"child_variety_id": "child-a", "parent_variety_id": "parent-a", "parent_order": 1}]
    assert missing_ids == ["child-b", "parent-b", "parent-c"]
