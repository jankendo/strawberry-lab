"""Small batching helpers for Supabase/PostgREST queries."""

from __future__ import annotations

from collections.abc import Iterable, Sequence


def chunked_sequence(values: Sequence[str], size: int) -> Iterable[list[str]]:
    """Yield a sequence in deterministic chunks."""
    if size <= 0:
        raise ValueError("size must be positive.")
    for index in range(0, len(values), size):
        yield list(values[index : index + size])
