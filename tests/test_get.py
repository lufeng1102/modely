"""Unit tests for unified get helpers."""

import pytest

from modely.get import _verify_download_checksums, download_resource
from modely.reliability import normalize_download_options
from modely.types import FileInfo, RepoRef


def test_verify_download_checksums_passes_matching_file(tmp_path, monkeypatch):
    local = tmp_path / "config.json"
    local.write_text("hello")
    expected = "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
    ref = RepoRef("hf", "model", "org/model", path="config.json")

    monkeypatch.setattr("modely.files.list_repo_files", lambda *a, **k: [FileInfo("config.json", sha256=expected)])

    statuses = _verify_download_checksums(str(local), ref, options=normalize_download_options(checksum=True))

    assert statuses[0]["ok"] is True
    assert statuses[0]["actual"] == expected


def test_verify_download_checksums_fails_mismatch(tmp_path, monkeypatch):
    local = tmp_path / "config.json"
    local.write_text("actual")
    ref = RepoRef("hf", "model", "org/model", path="config.json")

    monkeypatch.setattr("modely.files.list_repo_files", lambda *a, **k: [FileInfo("config.json", sha256="bad")])

    with pytest.raises(Exception, match="Checksum verification failed"):
        _verify_download_checksums(str(local), ref, options=normalize_download_options(checksum=True))


def test_verify_download_checksums_skips_missing_remote_checksum(tmp_path, monkeypatch):
    local = tmp_path / "config.json"
    local.write_text("actual")
    ref = RepoRef("hf", "model", "org/model", path="config.json")

    monkeypatch.setattr("modely.files.list_repo_files", lambda *a, **k: [FileInfo("config.json")])

    statuses = _verify_download_checksums(str(local), ref, options=normalize_download_options(checksum=True))

    assert statuses[0]["ok"] is True
    assert statuses[0]["skipped"] is True


def test_verify_download_checksums_maps_snapshot_paths(tmp_path, monkeypatch):
    nested = tmp_path / "nested" / "file.txt"
    nested.parent.mkdir()
    nested.write_text("hello")
    expected = "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
    ref = RepoRef("hf", "model", "org/model")

    monkeypatch.setattr("modely.files.list_repo_files", lambda *a, **k: [FileInfo("nested/file.txt", sha256=expected)])

    statuses = _verify_download_checksums(str(tmp_path), ref, options=normalize_download_options(checksum=True))

    assert statuses[0]["path"].endswith("nested/file.txt")
    assert statuses[0]["ok"] is True


def test_verify_download_checksums_noops_when_disabled(tmp_path, monkeypatch):
    ref = RepoRef("hf", "model", "org/model", path="config.json")

    def fail_if_called(*args, **kwargs):
        raise AssertionError("list_repo_files should not be called")

    monkeypatch.setattr("modely.files.list_repo_files", fail_if_called)

    assert _verify_download_checksums(str(tmp_path), ref, options=normalize_download_options(checksum=False)) == []


def test_verify_download_checksums_fails_missing_local_file(tmp_path, monkeypatch):
    ref = RepoRef("hf", "model", "org/model")
    monkeypatch.setattr("modely.files.list_repo_files", lambda *a, **k: [FileInfo("missing.txt", sha256="abc")])

    with pytest.raises(Exception, match="missing downloaded file"):
        _verify_download_checksums(str(tmp_path), ref, options=normalize_download_options(checksum=True))


def test_download_resource_wires_checksum_verification(tmp_path, monkeypatch):
    local = tmp_path / "config.json"
    local.write_text("hello")
    expected = "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"

    monkeypatch.setattr("modely.auth.get_token", lambda source, token=None: token)
    monkeypatch.setattr("modely.hf.hf_file_download", lambda *a, **k: str(local))
    monkeypatch.setattr("modely.files.list_repo_files", lambda *a, **k: [FileInfo("config.json", sha256=expected)])

    result = download_resource("hf://models/org/model", file="config.json", checksum=True)

    assert result == str(local)
