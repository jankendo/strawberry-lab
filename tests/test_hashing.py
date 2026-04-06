from scraper.utils.hashing import compute_article_hash, compute_variety_hash


def test_hashing_is_stable_for_whitespace_variants() -> None:
    h1 = compute_article_hash(" https://example.com/a ", " タイトル ", "本文  です")
    h2 = compute_article_hash("https://example.com/a", "タイトル", "本文 です")
    assert h1 == h2


def test_hashing_changes_when_content_changes() -> None:
    h1 = compute_article_hash("https://example.com/a", "タイトル", "本文")
    h2 = compute_article_hash("https://example.com/a", "タイトル", "本文変更")
    assert h1 != h2


def test_variety_hash_changes_when_registration_number_changes() -> None:
    h1 = compute_variety_hash("12345", "とちおとめ", "https://example.com/1")
    h2 = compute_variety_hash("99999", "とちおとめ", "https://example.com/1")
    assert h1 != h2
