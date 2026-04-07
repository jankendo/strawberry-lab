from types import SimpleNamespace

import pytest

from src.services import storage_service


class _FakeStorageBucket:
    def __init__(self, bucket: str, *, missing_paths: set[str] | None = None) -> None:
        self.bucket = bucket
        self.created: list[tuple[str, dict | None]] = []
        self.missing_paths = set(missing_paths or [])

    def create_signed_upload_url(self, path: str, options: dict | None = None) -> dict:
        self.created.append((path, options))
        return {"signed_url": f"https://example.supabase.co/storage/v1/{self.bucket}/{path}?token=abc"}

    def exists(self, path: str) -> bool:
        return path not in self.missing_paths


class _FakeStorage:
    def __init__(self, *, missing_paths: dict[str, set[str]] | None = None) -> None:
        self.buckets: dict[str, _FakeStorageBucket] = {}
        self.missing_paths = {bucket: set(paths) for bucket, paths in (missing_paths or {}).items()}

    def from_(self, bucket: str) -> _FakeStorageBucket:
        if bucket not in self.buckets:
            self.buckets[bucket] = _FakeStorageBucket(bucket, missing_paths=self.missing_paths.get(bucket))
        return self.buckets[bucket]


class _FakeTable:
    def __init__(self, name: str, client: "_FakeClient") -> None:
        self.name = name
        self.client = client
        self._mode = "count"
        self._insert_rows = None
        self._head = False

    def select(self, *_args, **_kwargs):
        self._mode = "count"
        self._head = bool(_kwargs.get("head"))
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def insert(self, rows):
        self._mode = "insert"
        self._insert_rows = rows
        return self

    def execute(self):
        if self._mode == "insert":
            payload = self._insert_rows or []
            self.client.inserted[self.name] = payload
            self.client.rows.setdefault(self.name, []).extend(payload)
            return SimpleNamespace(data=payload, count=None)
        if not self._head:
            payload = self.client.rows.get(self.name, [])
            return SimpleNamespace(data=payload, count=len(payload))
        count = self.client.counts.get(self.name, 0)
        return SimpleNamespace(data=[], count=count)


class _FakeClient:
    def __init__(
        self,
        *,
        counts: dict[str, int] | None = None,
        rows: dict[str, list[dict]] | None = None,
        missing_paths: dict[str, set[str]] | None = None,
    ) -> None:
        self.counts = dict(counts or {})
        self.rows = {name: [dict(row) for row in table_rows] for name, table_rows in (rows or {}).items()}
        self.inserted: dict[str, list[dict]] = {}
        self.storage = _FakeStorage(missing_paths=missing_paths)

    def table(self, name: str) -> _FakeTable:
        return _FakeTable(name, self)


def _sample_client_file(*, client_file_id: str, file_name: str = "sample.webp") -> dict:
    return {
        "client_file_id": client_file_id,
        "file_name": file_name,
        "mime_type": "image/webp",
        "file_size_bytes": 120_000,
        "width": 1024,
        "height": 768,
    }


def test_prepare_variety_image_direct_upload_targets_returns_signed_targets(monkeypatch) -> None:
    client = _FakeClient(counts={"variety_images": 1})
    monkeypatch.setattr(storage_service, "get_user_client", lambda: client)

    targets = storage_service.prepare_variety_image_direct_upload_targets(
        "variety-1",
        [
            _sample_client_file(client_file_id="file-1"),
            _sample_client_file(client_file_id="file-2", file_name="second.webp"),
        ],
    )

    assert len(targets) == 2
    assert targets[0]["client_file_id"] == "file-1"
    assert targets[0]["storage_path"].startswith("varieties/variety-1/")
    assert "signed_upload_url" in targets[0]
    assert targets[0]["mime_type"] == "image/webp"


def test_prepare_variety_image_direct_upload_targets_rejects_limit_overflow(monkeypatch) -> None:
    client = _FakeClient(counts={"variety_images": 4})
    monkeypatch.setattr(storage_service, "get_user_client", lambda: client)

    with pytest.raises(ValueError, match="最大5枚"):
        storage_service.prepare_variety_image_direct_upload_targets(
            "variety-1",
            [
                _sample_client_file(client_file_id="file-1"),
                _sample_client_file(client_file_id="file-2"),
            ],
        )


def test_prepare_variety_image_direct_upload_targets_accepts_signed_url_payload_variants(monkeypatch) -> None:
    client = _FakeClient()
    monkeypatch.setattr(storage_service, "get_user_client", lambda: client)
    bucket = client.storage.from_("variety-images")

    def _camel_case_signed_url(path: str, options: dict | None = None) -> dict:
        bucket.created.append((path, options))
        return {"signedUrl": f"https://example.supabase.co/storage/v1/variety-images/{path}?token=abc"}

    monkeypatch.setattr(bucket, "create_signed_upload_url", _camel_case_signed_url)

    targets = storage_service.prepare_variety_image_direct_upload_targets(
        "variety-1",
        [_sample_client_file(client_file_id="file-1")],
    )

    assert len(targets) == 1
    assert targets[0]["signed_upload_url"].startswith("https://example.supabase.co/storage/v1/variety-images/")


def test_prepare_variety_image_direct_upload_targets_raises_when_signed_url_missing(monkeypatch) -> None:
    client = _FakeClient()
    monkeypatch.setattr(storage_service, "get_user_client", lambda: client)
    bucket = client.storage.from_("variety-images")
    monkeypatch.setattr(bucket, "create_signed_upload_url", lambda _path, _options=None: {})

    with pytest.raises(RuntimeError, match="署名付きアップロードURLの生成に失敗しました。"):
        storage_service.prepare_variety_image_direct_upload_targets(
            "variety-1",
            [_sample_client_file(client_file_id="file-1")],
        )


def test_prepare_review_image_direct_upload_targets_rejects_oversized_long_edge(monkeypatch) -> None:
    client = _FakeClient()
    monkeypatch.setattr(storage_service, "get_user_client", lambda: client)

    oversized = _sample_client_file(client_file_id="file-1")
    oversized["width"] = 3000
    oversized["height"] = 1500

    with pytest.raises(ValueError, match="長辺"):
        storage_service.prepare_review_image_direct_upload_targets("review-1", [oversized])


def test_finalize_review_image_direct_uploads_inserts_metadata_rows(monkeypatch) -> None:
    client = _FakeClient(counts={"review_images": 0})
    monkeypatch.setattr(storage_service, "get_user_client", lambda: client)
    cache_cleared = {"called": False}
    monkeypatch.setattr(storage_service, "_clear_image_cache", lambda: cache_cleared.__setitem__("called", True))

    uploaded = [
        {
            "client_file_id": "file-1",
            "file_name": "sample.webp",
            "mime_type": "image/webp",
            "file_size_bytes": 130_000,
            "width": 1200,
            "height": 800,
            "storage_path": "reviews/review-1/path/sample.webp",
        }
    ]
    inserted = storage_service.finalize_review_image_direct_uploads("review-1", uploaded)

    assert len(inserted) == 1
    assert client.inserted["review_images"][0]["review_id"] == "review-1"
    assert client.inserted["review_images"][0]["storage_path"] == "reviews/review-1/path/sample.webp"
    assert cache_cleared["called"] is True


def test_finalize_review_image_direct_uploads_rejects_storage_path_for_other_relation(monkeypatch) -> None:
    client = _FakeClient(counts={"review_images": 0})
    monkeypatch.setattr(storage_service, "get_user_client", lambda: client)

    uploaded = [
        {
            "client_file_id": "file-1",
            "file_name": "sample.webp",
            "mime_type": "image/webp",
            "file_size_bytes": 130_000,
            "width": 1200,
            "height": 800,
            "storage_path": "reviews/review-2/path/sample.webp",
        }
    ]
    with pytest.raises(ValueError, match="ストレージパス"):
        storage_service.finalize_review_image_direct_uploads("review-1", uploaded)


def test_finalize_review_image_direct_uploads_rejects_storage_path_mime_mismatch(monkeypatch) -> None:
    client = _FakeClient(counts={"review_images": 0})
    monkeypatch.setattr(storage_service, "get_user_client", lambda: client)

    uploaded = [
        {
            "client_file_id": "file-1",
            "file_name": "sample.webp",
            "mime_type": "image/webp",
            "file_size_bytes": 130_000,
            "width": 1200,
            "height": 800,
            "storage_path": "reviews/review-1/path/sample.jpg",
        }
    ]
    with pytest.raises(ValueError, match="ストレージパス"):
        storage_service.finalize_review_image_direct_uploads("review-1", uploaded)


def test_finalize_variety_image_direct_uploads_deduplicates_storage_paths(monkeypatch) -> None:
    client = _FakeClient(counts={"variety_images": 0})
    monkeypatch.setattr(storage_service, "get_user_client", lambda: client)
    cache_cleared = {"called": False}
    monkeypatch.setattr(storage_service, "_clear_image_cache", lambda: cache_cleared.__setitem__("called", True))

    uploaded = [
        {
            "client_file_id": "file-1",
            "file_name": "sample.webp",
            "mime_type": "image/webp",
            "file_size_bytes": 130_000,
            "width": 1200,
            "height": 800,
            "storage_path": "varieties/variety-1/path/sample.webp",
        },
        {
            "client_file_id": "file-2",
            "file_name": "sample-copy.webp",
            "mime_type": "image/webp",
            "file_size_bytes": 130_000,
            "width": 1200,
            "height": 800,
            "storage_path": "varieties/variety-1/path/sample.webp",
        },
    ]
    inserted = storage_service.finalize_variety_image_direct_uploads("variety-1", uploaded)

    assert len(inserted) == 1
    assert len(client.inserted["variety_images"]) == 1
    assert cache_cleared["called"] is True


def test_finalize_variety_image_direct_uploads_rejects_limit_overflow(monkeypatch) -> None:
    client = _FakeClient(
        counts={"variety_images": 5},
        rows={
            "variety_images": [
                {"id": f"existing-{index}", "storage_path": f"varieties/variety-1/existing-{index}.webp"}
                for index in range(5)
            ]
        },
    )
    monkeypatch.setattr(storage_service, "get_user_client", lambda: client)

    uploaded = [
        {
            "client_file_id": "file-1",
            "file_name": "sample.webp",
            "mime_type": "image/webp",
            "file_size_bytes": 130_000,
            "width": 1200,
            "height": 800,
            "storage_path": "varieties/variety-1/path/sample.webp",
        }
    ]
    with pytest.raises(ValueError, match="最大5枚"):
        storage_service.finalize_variety_image_direct_uploads("variety-1", uploaded)


def test_finalize_review_image_direct_uploads_rejects_missing_storage_object(monkeypatch) -> None:
    client = _FakeClient(
        counts={"review_images": 0},
        missing_paths={"review-images": {"reviews/review-1/path/sample.webp"}},
    )
    monkeypatch.setattr(storage_service, "get_user_client", lambda: client)

    uploaded = [
        {
            "client_file_id": "file-1",
            "file_name": "sample.webp",
            "mime_type": "image/webp",
            "file_size_bytes": 130_000,
            "width": 1200,
            "height": 800,
            "storage_path": "reviews/review-1/path/sample.webp",
        }
    ]

    with pytest.raises(ValueError, match="アップロード済みファイルを確認できませんでした"):
        storage_service.finalize_review_image_direct_uploads("review-1", uploaded)


def test_finalize_variety_image_direct_uploads_skips_already_persisted_storage_paths(monkeypatch) -> None:
    client = _FakeClient(
        counts={"variety_images": 1},
        rows={
            "variety_images": [
                {
                    "id": "existing-row",
                    "storage_path": "varieties/variety-1/path/sample.webp",
                }
            ]
        },
    )
    monkeypatch.setattr(storage_service, "get_user_client", lambda: client)

    uploaded = [
        {
            "client_file_id": "file-1",
            "file_name": "sample.webp",
            "mime_type": "image/webp",
            "file_size_bytes": 130_000,
            "width": 1200,
            "height": 800,
            "storage_path": "varieties/variety-1/path/sample.webp",
        }
    ]

    inserted = storage_service.finalize_variety_image_direct_uploads("variety-1", uploaded)

    assert inserted == []
    assert "variety_images" not in client.inserted
