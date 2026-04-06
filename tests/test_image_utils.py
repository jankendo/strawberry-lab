import io

import pytest
from PIL import Image

from src.utils.image_utils import process_image, validate_image_file


def _make_jpeg(size=(4000, 3000)) -> bytes:
    image = Image.new("RGB", size, color=(255, 0, 0))
    out = io.BytesIO()
    image.save(out, format="JPEG")
    return out.getvalue()


def test_validate_image_file_accepts_jpeg() -> None:
    data = _make_jpeg()
    validate_image_file("sample.jpg", "image/jpeg", data)


def test_validate_image_file_rejects_bad_extension() -> None:
    data = _make_jpeg()
    with pytest.raises(ValueError):
        validate_image_file("sample.gif", "image/gif", data)


def test_process_image_resizes_to_max_long_edge() -> None:
    data = _make_jpeg((4096, 2048))
    processed = process_image(data, ".jpg")
    assert max(processed.width, processed.height) <= 2048
