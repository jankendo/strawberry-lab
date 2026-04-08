from pathlib import Path


def test_reviews_page_uses_slider_only_for_scores() -> None:
    source = Path("pages/02_reviews.py").read_text(encoding="utf-8")

    assert 'st.slider("甘味 *"' in source
    assert 'st.slider("酸味 *"' in source
    assert 'st.slider("香り *"' in source
    assert 'st.slider("食感 *"' in source
    assert 'st.slider("見た目 *"' in source
    assert "render_radar_input(" not in source
    assert 'key="review_score_radar"' not in source
    assert '_REVIEW_SCORE_BASELINE_KEY = "review_score_baseline"' not in source
