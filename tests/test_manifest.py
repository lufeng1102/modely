"""Unit tests for manifest and lock validation."""

from modely.manifest import read_manifest, validate_lock, write_manifest
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
