from src.components import offline_queue
from src.components.offline_queue import _normalize_event_name, _normalize_intent_id, _normalize_queue_key


def test_normalize_queue_key_sanitizes_and_falls_back() -> None:
    assert _normalize_queue_key(" notes/save queue ") == "notes-save-queue"
    assert _normalize_queue_key("   ", fallback="fallback-queue") == "fallback-queue"


def test_normalize_intent_id_uses_fallback_when_input_invalid() -> None:
    assert _normalize_intent_id("###", fallback="intent-fallback") == "intent-fallback"


def test_normalize_event_name_preserves_supported_separators() -> None:
    assert _normalize_event_name("ichigodb:notes/save replay") == "ichigodb:notes-save-replay"


def test_render_offline_intent_queue_bridge_normalizes_replay_event_and_ack(monkeypatch) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(offline_queue, "_inject", lambda config: captured.update(config))

    offline_queue.render_offline_intent_queue_bridge(
        " reviews/image upload queue ",
        queue_label="",
        replay_event_name="ichigodb:reviews/image replay",
    )

    assert captured["mode"] == "bridge"
    assert captured["queueKey"] == "reviews-image-upload-queue"
    assert captured["queueLabel"] == "保存キュー"
    assert captured["replayEventName"] == "ichigodb:reviews-image-replay"
    assert captured["replayAckEventName"] == "ichigodb:reviews-image-replay:ack"


def test_trigger_offline_intent_replay_normalizes_reason_and_queue(monkeypatch) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(offline_queue, "_inject", lambda config: captured.update(config))

    offline_queue.trigger_offline_intent_replay(
        " reviews/image upload queue ",
        reason="",
        replay_event_name="ichigodb:reviews/image replay",
    )

    assert captured["mode"] == "request_replay"
    assert captured["queueKey"] == "reviews-image-upload-queue"
    assert captured["reason"] == "manual"
    assert captured["replayEventName"] == "ichigodb:reviews-image-replay"
    assert captured["replayAckEventName"] == "ichigodb:reviews-image-replay:ack"


def test_notify_offline_intent_replayed_normalizes_processed_ids(monkeypatch) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(offline_queue, "_inject", lambda config: captured.update(config))

    offline_queue.notify_offline_intent_replayed(
        " reviews/image upload queue ",
        processed_ids=[" intent-1 ", "intent 2", ""],
        replayed_count=2,
        clear_all=True,
        message="replayed",
        replay_event_name="ichigodb:reviews/image replay",
    )

    assert captured["mode"] == "notify_replayed"
    assert captured["queueKey"] == "reviews-image-upload-queue"
    assert captured["processedIds"] == ["intent-1", "intent-2"]
    assert captured["replayedCount"] == 2
    assert captured["clearAll"] is True
    assert captured["message"] == "replayed"
