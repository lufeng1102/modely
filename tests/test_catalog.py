"""Unit tests for local and cache catalog helpers."""

import json

from modely.catalog import catalog_from_cache, catalog_from_directory, print_catalog_report, scan_catalog
from modely.manifest import write_manifest
from modely.types import DownloadManifest, FileInfo


def test_catalog_from_directory_detects_asset(tmp_path):
    model = tmp_path / "model-a"
    model.mkdir()
    (model / "config.json").write_text("{}")
    (model / "tokenizer.json").write_text("{}")

    entries = catalog_from_directory(str(tmp_path))

    assert len(entries) == 1
    assert entries[0].id == "model-a"
    assert entries[0].file_count == 2
    assert entries[0].size > 0


def test_catalog_from_directory_uses_lock_metadata(tmp_path):
    model = tmp_path / "model-a"
    model.mkdir()
    (model / "config.json").write_text("{}")
    lock = model / "modely.lock"
    write_manifest(DownloadManifest("hf", "model", "org/model", revision="main", files=[FileInfo("config.json", size=2)]), str(lock))

    entry = catalog_from_directory(str(tmp_path))[0]

    assert entry.source == "hf"
    assert entry.repo_type == "model"
    assert entry.repo_id == "org/model"
    assert entry.revision == "main"
    assert entry.lock_path == str(lock)


def test_catalog_from_cache(monkeypatch):
    monkeypatch.setattr("modely.catalog.cache.list_cache", lambda cache_dir=None, detail=True: [
        {
            "source": "hf",
            "repo_type": "model",
            "repo_id": "org/model",
            "revision": "main",
            "path": "/tmp/cache/model",
            "size": 123,
            "size_str": "123 B",
            "files": [{"name": "config.json", "size": 2}],
        }
    ])

    entries = catalog_from_cache("/tmp/cache")

    assert len(entries) == 1
    assert entries[0].source == "hf"
    assert entries[0].file_count == 1
    assert entries[0].metadata["origin"] == "cache"


def test_scan_catalog_summary_and_enrichment_skip(tmp_path):
    model = tmp_path / "model-a"
    model.mkdir()
    (model / "config.json").write_text("{}")

    report = scan_catalog(str(tmp_path), include_scores=True, include_scan=True, use_remote=False)

    assert report.summary["total_entries"] == 1
    assert report.summary["by_source"] == {"unknown": 1}
    assert "score/scan enrichment skipped" in report.warnings[0]


def test_print_catalog_json(tmp_path, capsys):
    model = tmp_path / "model-a"
    model.mkdir()
    (model / "config.json").write_text("{}")

    print_catalog_report(scan_catalog(str(tmp_path)), as_json=True)
    parsed = json.loads(capsys.readouterr().out)

    assert parsed["summary"]["total_entries"] == 1
    assert parsed["entries"][0]["id"] == "model-a"


def test_print_catalog_human(tmp_path, capsys):
    model = tmp_path / "model-a"
    model.mkdir()
    (model / "config.json").write_text("{}")

    print_catalog_report(scan_catalog(str(tmp_path)))
    out = capsys.readouterr().out

    assert "Total entries" in out
    assert "model-a" in out


def test_scan_catalog_from_cache(monkeypatch):
    monkeypatch.setattr("modely.catalog.cache.get_cache_dir", lambda cache_dir=None: "/tmp/cache")
    monkeypatch.setattr("modely.catalog.cache.list_cache", lambda cache_dir=None, detail=True: [
        {"source": "ms", "repo_type": "dataset", "repo_id": "org/data", "revision": "v1", "path": "/tmp/data", "size": 10, "files": []}
    ])

    report = scan_catalog(from_cache=True)

    assert report.root == "/tmp/cache"
    assert report.summary["by_source"] == {"ms": 1}
