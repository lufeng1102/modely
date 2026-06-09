"""Unit tests for resource comparison."""

from modely.compare import compare_resources
from modely.types import AssetAnalysis, FileSummary, RepoInfo


def fake_analysis(source, repo_id, license, tags, size, files):
    return AssetAnalysis(
        info=RepoInfo(source, "model", repo_id, license=license, tags=tags),
        summary=FileSummary(total_files=files, total_size=size, selected_files=files, selected_size=size),
        has_config=True,
        has_tokenizer=True,
        has_card=True,
    )


def test_compare_resources_computes_deltas(monkeypatch):
    values = [
        fake_analysis("hf", "org/a", "mit", ["nlp", "qwen"], 100, 3),
        fake_analysis("ms", "org/a", "apache-2.0", ["nlp"], 50, 2),
    ]
    monkeypatch.setattr("modely.compare.analyze_resource", lambda *a, **k: values.pop(0))

    result = compare_resources("hf://models/org/a", "ms://models/org/a")

    assert result.same_license is False
    assert result.size_delta == 50
    assert result.file_count_delta == 1
    assert result.shared_tags == ["nlp"]
    assert result.different_tags["left_only"] == ["qwen"]
