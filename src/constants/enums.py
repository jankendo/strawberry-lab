"""Shared enum definitions."""

from __future__ import annotations

from enum import Enum


class AcidityLevel(str, Enum):
    """Allowed acidity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


class ScrapeRunStatus(str, Enum):
    """Overall scrape run statuses."""

    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"
    PARTIAL_SUCCESS = "partial_success"
