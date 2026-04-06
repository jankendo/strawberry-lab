from src.components.offline_queue import _normalize_event_name, _normalize_intent_id, _normalize_queue_key


def test_normalize_queue_key_sanitizes_and_falls_back() -> None:
    assert _normalize_queue_key(" notes/save queue ") == "notes-save-queue"
    assert _normalize_queue_key("   ", fallback="fallback-queue") == "fallback-queue"


def test_normalize_intent_id_uses_fallback_when_input_invalid() -> None:
    assert _normalize_intent_id("###", fallback="intent-fallback") == "intent-fallback"


def test_normalize_event_name_preserves_supported_separators() -> None:
    assert _normalize_event_name("ichigodb:notes/save replay") == "ichigodb:notes-save-replay"
