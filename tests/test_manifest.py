"""Unit tests for manifest and lock validation."""

from modely.manifest import create_lock, lock_summary, read_manifest, validate_lock, write_manifest
from modely.types import DownloadManifest, FileInfo


def test_validate_lock_reports_missing_file(tmp_path):
    lock = tmp_path / "modely.lock"
    write_manifest(DownloadManifest("hf", "model", "gpt2", files=[FileInfo("config.json")]), str(lock))

    result = validate_lock(str(lock), local_dir=str(tmp_path))

    assert result["ok"] is False
    assert result["missing_files"] == ["config.json"]


def test_validate_lock_checksum_mismatch(tmp_path):
    local = tmp_path / "config.json"
    local.write_text("actual")
    lock = tmp_path / "modely.lock"
    write_manifest(DownloadManifest("hf", "model", "gpt2", files=[FileInfo("config.json", sha256="bad")]), str(lock))

    result = validate_lock(str(lock), local_dir=str(tmp_path), checksum=True)

    assert result["ok"] is False
    assert result["checksum_mismatches"][0]["path"] == "config.json"


def test_read_manifest_tolerates_missing_metadata(tmp_path):
    lock = tmp_path / "old.lock"
    lock.write_text('{"source":"hf","repo_type":"model","repo_id":"gpt2","files":[]}')
    manifest = read_manifest(str(lock))
    assert manifest.metadata == {}


def test_create_lock_resolves_profile_and_metadata(tmp_path, monkeypatch):
    captured = {}

    def fake_list(ref, **kwargs):
        captured["endpoint"] = kwargs.get("endpoint")
        return [
            FileInfo("README.md", size=10, sha256="a"),
            FileInfo("config.json", size=20, sha256="b"),
            FileInfo("model.bin", size=100),
        ]

    monkeypatch.setattr("modely.manifest.list_repo_files", fake_list)
    output = tmp_path / "modely.lock"

    manifest = create_lock("hf://models/gpt2", profile="minimal", endpoint="https://hf.example", output=str(output))

    assert captured["endpoint"] == "https://hf.example"
    assert manifest.metadata["schema_version"] == 2
    assert manifest.metadata["profile"] == "minimal"
    assert manifest.metadata["resource"] == "hf://models/gpt2"
    assert manifest.metadata["file_count"] == 2
    assert manifest.metadata["checksum_count"] == 2
    assert all(f.path != "model.bin" for f in manifest.files)


def test_lock_summary_counts_checksums():
    manifest = DownloadManifest("hf", "model", "gpt2", files=[FileInfo("a", size=10, sha256="x"), FileInfo("b", size=5)])

    summary = lock_summary(manifest)

    assert summary == {"file_count": 2, "total_size": 15, "checksum_count": 1, "missing_checksum_count": 1}
