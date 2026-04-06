"""Date and timezone helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo


def now_utc() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(tz=UTC)


def to_jst_iso8601(value: datetime | None) -> str:
    """Convert datetime to JST ISO8601 string."""
    if value is None:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(ZoneInfo("Asia/Tokyo")).isoformat()
