"""Batch search and download helpers for modely-ai."""

from __future__ import annotations

from typing import Iterable, Sequence

from .search import SearchResult


def filter_results_by_tags(results: Iterable[SearchResult], tags: Sequence[str]) -> list[SearchResult]:
    """Return results whose tags contain all requested tags, case-insensitively."""
    required = {str(tag).strip().lower() for tag in tags if str(tag).strip()}
    if not required:
        raise ValueError("at least one tag is required")

    filtered: list[SearchResult] = []
    for result in results:
        available = {str(tag).strip().lower() for tag in (result.tags or []) if str(tag).strip()}
        if required.issubset(available):
            filtered.append(result)
    return filtered
