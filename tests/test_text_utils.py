from src.utils.text_utils import build_search_key, normalize_search_text


def test_normalize_search_text_folds_hiragana_and_katakana_together() -> None:
    assert normalize_search_text("さがほのか") == normalize_search_text("サガホノカ")


def test_build_search_key_includes_aliases_for_kana_matching() -> None:
    search_key = build_search_key(["サガホノカ", ["さがほのか", "砂糖苺"]])

    assert normalize_search_text("さが") in search_key
    assert normalize_search_text("サガ") in search_key
