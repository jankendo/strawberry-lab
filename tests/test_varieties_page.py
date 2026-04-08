from pathlib import Path


def test_varieties_page_keeps_saved_edit_target_and_exposes_edit_actions() -> None:
    source = Path("pages/01_varieties.py").read_text(encoding="utf-8")

    assert '_VARIETY_ACTIVE_SECTION_KEY = "variety_active_section"' in source
    assert '_VARIETY_ACTIVE_SECTION_REQUEST_KEY = "variety_active_section_requested"' in source
    assert '_VARIETY_EDIT_TARGET_KEY = "variety_edit_target_id"' in source
    assert '_VARIETY_EDIT_TARGET_REQUEST_KEY = "variety_edit_target_requested_id"' in source
    assert "def _set_variety_edit_target" in source
    assert "def _queue_variety_active_section" in source
    assert "def _consume_variety_active_section_request" in source
    assert "✏️ この品種を編集" in source
    assert '_set_variety_edit_target(pending_upload_task["target_id"])' in source
    assert 'st.session_state[_VARIETY_EDIT_TARGET_REQUEST_KEY]' in source
    assert 'st.session_state[_VARIETY_ACTIVE_SECTION_REQUEST_KEY]' in source
    assert 'st.session_state["variety_active_section"] = "作成・編集"' not in source


def test_varieties_page_explains_ready_state_and_upload_save_action() -> None:
    source = Path("pages/01_varieties.py").read_text(encoding="utf-8")

    assert "画像は保存待ちです。下のボタンで保存するとアップロードが始まります。" in source
    assert 'save_label = f"{save_label}して画像をアップロード"' in source
