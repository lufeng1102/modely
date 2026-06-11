"""Tests for tag-based batch download helpers."""

import pytest

from modely.batch import filter_results_by_tags
from modely.search import SearchResult


def test_filter_results_by_tags_requires_all_requested_tags():
    results = [
        SearchResult(id="org/matching", source="hf", repo_type="model", tags=["text-generation", "transformers"]),
        SearchResult(id="org/partial", source="hf", repo_type="model", tags=["text-generation"]),
        SearchResult(id="org/other", source="hf", repo_type="model", tags=["transformers", "vision"]),
    ]

    filtered = filter_results_by_tags(results, ["text-generation", "transformers"])

    assert [item.id for item in filtered] == ["org/matching"]


def test_filter_results_by_tags_matches_case_insensitively():
    results = [SearchResult(id="org/model", source="hf", repo_type="model", tags=["Text-Generation", "Transformers"])]

    filtered = filter_results_by_tags(results, ["text-generation", "TRANSFORMERS"])

    assert [item.id for item in filtered] == ["org/model"]


def test_filter_results_by_tags_rejects_empty_tags():
    with pytest.raises(ValueError, match="at least one tag"):
        filter_results_by_tags([], [])
