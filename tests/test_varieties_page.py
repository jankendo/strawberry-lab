from pathlib import Path


def test_varieties_page_keeps_saved_edit_target_and_exposes_edit_actions() -> None:
    source = Path("pages/01_varieties.py").read_text(encoding="utf-8")

    assert '_VARIETY_EDIT_TARGET_KEY = "variety_edit_target_id"' in source
    assert '_VARIETY_EDIT_TARGET_REQUEST_KEY = "variety_edit_target_requested_id"' in source
    assert "def _set_variety_edit_target" in source
    assert "✏️ この品種を編集" in source
    assert '_set_variety_edit_target(pending_upload_task["target_id"])' in source
    assert 'st.session_state[_VARIETY_EDIT_TARGET_REQUEST_KEY]' in source


def test_varieties_page_explains_ready_state_and_upload_save_action() -> None:
    source = Path("pages/01_varieties.py").read_text(encoding="utf-8")

    assert "画像は保存待ちです。下のボタンで保存するとアップロードが始まります。" in source
    assert 'save_label = f"{save_label}して画像をアップロード"' in source
