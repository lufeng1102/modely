"""Tests for tag-based batch download helpers."""

import json
import sys

import pytest

import modely
from modely.batch import create_batch_download_plan, filter_results_by_tags, run_batch_download
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


def test_create_batch_download_plan_filters_and_limits(monkeypatch):
    def fake_search(**kwargs):
        assert kwargs["keyword"] == "qwen"
        assert kwargs["source"] == "hf"
        assert kwargs["repo_type"] == "model"
        assert kwargs["limit"] == 10
        return [
            SearchResult(id="org/one", source="hf", repo_type="model", tags=["text-generation", "transformers"]),
            SearchResult(id="org/two", source="hf", repo_type="model", tags=["text-generation", "transformers"]),
            SearchResult(id="org/skip", source="hf", repo_type="model", tags=["text-generation"]),
        ]

    monkeypatch.setattr("modely.batch.search", fake_search)

    plan = create_batch_download_plan("qwen", source="hf", repo_type="model", tags=["text-generation", "transformers"], limit=1, search_limit=10)

    assert plan["dry_run"] is True
    assert plan["matched_count"] == 2
    assert [item["resource"] for item in plan["downloads"]] == ["hf://models/org/one"]


def test_create_batch_download_plan_rejects_empty_tags():
    with pytest.raises(ValueError, match="at least one tag"):
        create_batch_download_plan("qwen", tags=[])


def test_run_batch_download_calls_download_resource(monkeypatch):
    plan = {
        "downloads": [
            {"resource": "hf://models/org/one"},
            {"resource": "ms://models/org/two"},
        ]
    }
    calls = []

    def fake_download(resource, **kwargs):
        calls.append({"resource": resource, **kwargs})
        return f"/tmp/{resource.rsplit('/', 1)[-1]}"

    monkeypatch.setattr("modely.batch.download_resource", fake_download)

    result = run_batch_download(plan, local_dir="./models", profile="minimal", include=["*.json"], exclude=["*.bin"], prefer="hf,ms", fallback=True, retries=2, timeout=5, checksum=True, resume=False)

    assert result["ok"] is True
    assert [call["resource"] for call in calls] == ["hf://models/org/one", "ms://models/org/two"]
    assert calls[0]["local_dir"] == "./models"
    assert calls[0]["profile"] == "minimal"
    assert calls[0]["include"] == ["*.json"]
    assert calls[0]["exclude"] == ["*.bin"]
    assert calls[0]["fallback"] is True
    assert calls[0]["resume"] is False


def test_run_batch_download_reports_failures(monkeypatch):
    plan = {"downloads": [{"resource": "hf://models/good"}, {"resource": "hf://models/bad"}]}

    def fake_download(resource, **kwargs):
        if resource.endswith("bad"):
            raise RuntimeError("boom")
        return "/tmp/good"

    monkeypatch.setattr("modely.batch.download_resource", fake_download)

    result = run_batch_download(plan)

    assert result["ok"] is False
    assert result["summary"] == {"total": 2, "succeeded": 1, "failed": 1}
    assert result["results"][1]["error"] == "boom"


def test_batch_download_plan_json_serializable(monkeypatch):
    monkeypatch.setattr("modely.batch.search", lambda **kwargs: [SearchResult(id="org/model", source="hf", repo_type="model", tags=["tag"])] )

    plan = create_batch_download_plan(None, tags=["tag"])

    assert json.loads(json.dumps(plan))["downloads"][0]["resource"] == "hf://models/org/model"


def test_batch_download_cli_dry_run(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["modely", "batch-download", "qwen", "--tag", "tag", "--json"])
    monkeypatch.setattr(
        "modely.batch.search",
        lambda **kwargs: [SearchResult(id="org/model", source="hf", repo_type="model", tags=["tag"])],
    )

    modely.main()

    output = json.loads(capsys.readouterr().out)
    assert output["dry_run"] is True
    assert output["downloads"][0]["resource"] == "hf://models/org/model"


def test_batch_download_cli_execute_exits_nonzero_on_failure(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["modely", "batch-download", "qwen", "--tag", "tag", "--yes"])
    monkeypatch.setattr(
        "modely.batch.search",
        lambda **kwargs: [SearchResult(id="org/model", source="hf", repo_type="model", tags=["tag"])],
    )
    monkeypatch.setattr("modely.batch.download_resource", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))

    with pytest.raises(SystemExit) as exc:
        modely.main()

    assert exc.value.code == 1
    assert "Failures:" in capsys.readouterr().out
