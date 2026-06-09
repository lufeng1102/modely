"""Unit tests for planning helpers."""

from modely.types import FileInfo
from modely.plan import create_download_plan


def test_create_download_plan_filters_and_summarizes(monkeypatch, tmp_path):
    files = [
        FileInfo("config.json", size=10),
        FileInfo("tokenizer.json", size=20),
        FileInfo("model.safetensors", size=1000),
        FileInfo("nested", type="tree"),
    ]
    monkeypatch.setattr("modely.plan.list_repo_files", lambda *args, **kwargs: files)

    plan = create_download_plan("hf://models/gpt2", profile="no-weights", cache_dir=str(tmp_path))

    assert plan.source == "hf"
    assert [f.path for f in plan.files] == ["config.json", "tokenizer.json"]
    assert plan.summary.total_files == 3
    assert plan.summary.selected_files == 2
    assert plan.summary.categories["config"] == 1
    assert plan.summary.categories["tokenizer"] == 1


def test_plain_repo_plan_defaults_to_hf(monkeypatch, tmp_path):
    monkeypatch.setattr("modely.plan.list_repo_files", lambda *args, **kwargs: [])
    plan = create_download_plan("gpt2", cache_dir=str(tmp_path))
    assert plan.source == "hf"
    assert plan.warnings
