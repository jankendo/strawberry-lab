from pathlib import Path

from src.components import asset_uploader
from src.components.asset_uploader import _normalize_component_payload, _normalize_upload_targets


def test_normalize_upload_targets_filters_invalid_entries() -> None:
    targets = _normalize_upload_targets(
        [
            {
                "client_file_id": "file-1",
                "file_name": "a.webp",
                "mime_type": "image/webp",
                "file_size_bytes": 1200,
                "width": 400,
                "height": 300,
                "storage_path": "reviews/r1/a.webp",
                "signed_upload_url": "https://example/upload",
            },
            {
                "client_file_id": "file-2",
                "file_name": "b.webp",
                "mime_type": "image/webp",
                "file_size_bytes": 1400,
                "width": 400,
                "height": 300,
                "storage_path": "",
                "signed_upload_url": "https://example/upload",
            },
        ],
        max_files=3,
    )

    assert len(targets) == 1
    assert targets[0]["client_file_id"] == "file-1"


def test_normalize_component_payload_tracks_uploaded_and_failed_entries() -> None:
    payload = _normalize_component_payload(
        {
            "status": "uploaded",
            "files": [
                {
                    "client_file_id": "file-1",
                    "file_name": "a.webp",
                    "mime_type": "image/webp",
                    "file_size_bytes": 1200,
                    "width": 400,
                    "height": 300,
                }
            ],
            "uploaded": [
                {
                    "client_file_id": "file-1",
                    "file_name": "a.webp",
                    "mime_type": "image/webp",
                    "file_size_bytes": 1200,
                    "width": 400,
                    "height": 300,
                    "storage_path": "reviews/r1/a.webp",
                    "upload_request_token": "token-1",
                    "http_status": 200,
                }
            ],
            "failed": [
                {
                    "client_file_id": "file-2",
                    "file_name": "b.webp",
                    "mime_type": "image/webp",
                    "file_size_bytes": 1500,
                    "width": 300,
                    "height": 300,
                    "storage_path": "reviews/r1/b.webp",
                    "upload_request_token": "token-1",
                    "error": "network",
                }
            ],
            "pending_count": 1,
            "last_processed_upload_token": "token-1",
        },
        max_files=3,
    )

    assert payload["status"] == "uploaded"
    assert len(payload["files"]) == 1
    assert len(payload["uploaded"]) == 1
    assert len(payload["failed"]) == 1
    assert payload["pending_count"] == 1
    assert payload["last_processed_upload_token"] == "token-1"


def test_normalize_component_payload_normalizes_debug_messages_and_invalid_status() -> None:
    payload = _normalize_component_payload(
        {
            "status": "unknown",
            "debug_messages": [" first ", "", 42, None],
        },
        max_files=3,
    )

    assert payload["status"] == "idle"
    assert payload["debug_messages"] == ["first", "42"]


def test_render_asset_uploader_returns_fallback_payload_when_component_raises(monkeypatch) -> None:
    def _raise_component(**_kwargs):
        raise RuntimeError("component load failed")

    monkeypatch.setattr(asset_uploader, "_ASSET_UPLOADER_COMPONENT", _raise_component)
    monkeypatch.setattr(asset_uploader.st, "caption", lambda *_args, **_kwargs: None)

    payload = asset_uploader.render_asset_uploader(key="test-asset-uploader")

    assert payload["component_available"] is False
    assert payload["status"] == "idle"
    assert payload["files"] == []
    assert payload["debug_messages"] == ["component_init_error:RuntimeError:component load failed"]


def test_render_asset_uploader_returns_debug_reason_when_component_missing(monkeypatch) -> None:
    monkeypatch.setattr(asset_uploader, "_ASSET_UPLOADER_COMPONENT", None)
    monkeypatch.setattr(asset_uploader.st, "caption", lambda *_args, **_kwargs: None)

    payload = asset_uploader.render_asset_uploader(key="test-asset-uploader")

    assert payload["component_available"] is False
    assert payload["debug_messages"] == ["component_unavailable:asset_uploader_component_missing"]


def test_render_asset_uploader_normalizes_replay_event_and_queue_key(monkeypatch) -> None:
    captured_kwargs = {}

    def _fake_component(**kwargs):
        captured_kwargs.update(kwargs)
        return {}

    monkeypatch.setattr(asset_uploader, "_ASSET_UPLOADER_COMPONENT", _fake_component)

    payload = asset_uploader.render_asset_uploader(
        key="test-asset-uploader",
        replay_event_name="ichigodb:reviews/image replay",
        replay_queue_key=" reviews/image upload queue ",
    )

    assert captured_kwargs["replayEventName"] == "ichigodb:reviews-image-replay"
    assert captured_kwargs["replayQueueKey"] == "reviews-image-upload-queue"
    assert payload["component_available"] is True


def test_asset_uploader_component_snapshots_selected_files_before_reset() -> None:
    source = (Path(asset_uploader._COMPONENT_DIR) / "index.html").read_text(encoding="utf-8")

    assert "const files = event && event.target ? Array.from(event.target.files || []) : [];" in source
    assert 'instance.status = "error";' in source
    assert "処理失敗: 画像の最適化に失敗しました。別の画像で再試行してください。" in source
