"""Image validation and optimization utilities."""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
MAX_LONG_EDGE = 2048


@dataclass(frozen=True)
class ProcessedImage:
    """Processed image output."""

    bytes_data: bytes
    mime_type: str
    width: int
    height: int
    file_size_bytes: int
    extension: str


def validate_image_file(file_name: str, mime_type: str, raw_bytes: bytes) -> None:
    """Run extension, mime type, size, and Pillow integrity checks."""
    ext = Path(file_name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError("許可されていない拡張子です。")
    if mime_type not in ALLOWED_MIME_TYPES:
        raise ValueError("許可されていないMIMEタイプです。")
    if len(raw_bytes) > MAX_UPLOAD_BYTES:
        raise ValueError("ファイルサイズが上限50MBを超えています。")
    try:
        Image.open(io.BytesIO(raw_bytes)).verify()
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("画像ファイルが破損している可能性があります。") from exc


def process_image(raw_bytes: bytes, original_extension: str) -> ProcessedImage:
    """Strip EXIF and resize image while preserving aspect ratio."""
    with Image.open(io.BytesIO(raw_bytes)) as image:
        image = image.convert("RGB") if image.mode in ("RGBA", "P") and original_extension.lower() in {".jpg", ".jpeg"} else image.copy()
        image.thumbnail((MAX_LONG_EDGE, MAX_LONG_EDGE))
        out = io.BytesIO()
        ext = original_extension.lower()
        if ext in {".jpg", ".jpeg"}:
            image.convert("RGB").save(out, format="JPEG", quality=85, optimize=True)
            mime = "image/jpeg"
            out_ext = ".jpg"
        elif ext == ".png":
            image.save(out, format="PNG", optimize=True)
            mime = "image/png"
            out_ext = ".png"
        else:
            image.save(out, format="WEBP", quality=85, method=6)
            mime = "image/webp"
            out_ext = ".webp"
        data = out.getvalue()
        return ProcessedImage(
            bytes_data=data,
            mime_type=mime,
            width=image.width,
            height=image.height,
            file_size_bytes=len(data),
            extension=out_ext,
        )
