from src.utils.variety_options import build_variety_option_search_key, filter_variety_selection_options


def test_filter_variety_selection_options_matches_hiragana_to_katakana() -> None:
    varieties = [
        {"id": "moka", "name": "モカベリー", "alias_names": []},
        {"id": "saga", "name": "さがほのか", "alias_names": []},
    ]

    filtered = filter_variety_selection_options(varieties, "もかべりー")

    assert [row["id"] for row in filtered] == ["moka"]


def test_filter_variety_selection_options_keeps_included_ids_when_keyword_has_no_match() -> None:
    varieties = [
        {"id": "moka", "name": "モカベリー", "alias_names": []},
        {"id": "saga", "name": "さがほのか", "alias_names": []},
    ]

    filtered = filter_variety_selection_options(varieties, "一致しない検索語", include_ids=("saga",))

    assert [row["id"] for row in filtered] == ["saga"]


def test_build_variety_option_search_key_includes_registration_metadata() -> None:
    search_key = build_variety_option_search_key(
        {
            "id": "moka",
            "name": "モカベリー",
            "alias_names": [],
            "registration_number": "品種登録12345",
            "application_number": "出願98765",
        }
    )

    assert "12345" in search_key
    assert "98765" in search_key
