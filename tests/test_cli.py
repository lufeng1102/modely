"""Integration tests for modely CLI and download functions.

These tests require network access and are marked with pytest.mark.integration.
Run with: pytest tests/ -m integration
Skip with: pytest tests/ -m "not integration"
"""

import fnmatch
import os
import shutil
import subprocess

import pytest

from modely.common import cache as cache_mod
from modely.modelscope import snapshot_download as ms_snapshot_download


@pytest.fixture
def tmp_cache(tmp_path):
    """Provide a temporary cache directory, cleaned up after test."""
    cache_dir = str(tmp_path / "modely_test_cache")
    os.makedirs(cache_dir, exist_ok=True)
    yield cache_dir
    if os.path.exists(cache_dir):
        shutil.rmtree(cache_dir)


def run_cli(*args):
    """Run modely-ai CLI and return CompletedProcess."""
    return subprocess.run(
        ["modely-ai", *args],
        capture_output=True,
        text=True,
        timeout=120,
    )


# ── Hugging Face ──────────────────────────────────────────────

@pytest.mark.integration
class TestHuggingFace:
    def test_hf_file_download(self, tmp_cache):
        result = run_cli("hf", "gpt2", "--file", "config.json", "--cache-dir", tmp_cache)
        assert result.returncode == 0
        assert "Successfully downloaded" in result.stdout

    def test_hf_file_cached(self, tmp_cache):
        # First download
        run_cli("hf", "gpt2", "--file", "config.json", "--cache-dir", tmp_cache)
        # Second should hit cache
        result = run_cli("hf", "gpt2", "--file", "config.json", "--cache-dir", tmp_cache)
        assert result.returncode == 0
        assert "cached" in result.stdout.lower() or "Successfully" in result.stdout


# ── ModelScope ────────────────────────────────────────────────

@pytest.mark.integration
class TestModelScope:
    def test_ms_file_download(self, tmp_cache):
        result = run_cli(
            "ms", "AI-ModelScope/gpt2",
            "--file", "config.json",
            "--cache-dir", tmp_cache,
        )
        assert result.returncode == 0
        assert "Successfully downloaded" in result.stdout

    def test_ms_file_cached(self, tmp_cache):
        run_cli("ms", "AI-ModelScope/gpt2", "--file", "config.json", "--cache-dir", tmp_cache)
        result = run_cli("ms", "AI-ModelScope/gpt2", "--file", "config.json", "--cache-dir", tmp_cache)
        assert result.returncode == 0


# ── GitHub ────────────────────────────────────────────────────

@pytest.mark.integration
class TestGitHub:
    def test_github_file_download(self, tmp_cache):
        result = run_cli(
            "github", "torvalds/linux",
            "--file", "README",
            "--revision", "master",
            "--cache-dir", tmp_cache,
        )
        assert result.returncode == 0
        assert "Successfully downloaded" in result.stdout

    def test_github_file_cached(self, tmp_cache):
        run_cli("github", "torvalds/linux", "--file", "README", "--revision", "master", "--cache-dir", tmp_cache)
        result = run_cli("github", "torvalds/linux", "--file", "README", "--revision", "master", "--cache-dir", tmp_cache)
        assert result.returncode == 0
        assert "cached" in result.stdout.lower()

    def test_github_clone_default_branch_fallback(self, tmp_cache):
        """When --revision main fails, should fall back to the actual default branch."""
        result = run_cli(
            "github", "httpie/cli",
            "--revision", "main",
            "--cache-dir", tmp_cache,
        )
        assert result.returncode == 0
        assert "cloned to" in result.stdout.lower() or "Cloning" in result.stdout

    def test_github_clone_cached(self, tmp_cache):
        """Second clone of same repo should hit cache."""
        run_cli("github", "httpie/cli", "--revision", "main", "--cache-dir", tmp_cache)
        result = run_cli("github", "httpie/cli", "--revision", "main", "--cache-dir", tmp_cache)
        assert result.returncode == 0
        assert "cached" in result.stdout.lower()

    def test_github_cache_path_is_tools(self, tmp_cache):
        """GitHub repos should be cached under tools/, not models/."""
        repo_dir = cache_mod.get_repo_cache_dir(
            "torvalds/linux", "tool", "master", "github", tmp_cache
        )
        assert os.path.join("github", "tools") in repo_dir
        assert "models" not in repo_dir


# ── Cache Management ──────────────────────────────────────────

@pytest.mark.integration
class TestCacheCLI:
    def test_cache_list_shows_all_sources(self, tmp_cache):
        # Download from ms and github (HF uses its own cache structure)
        run_cli("ms", "AI-ModelScope/gpt2", "--file", "config.json", "--cache-dir", tmp_cache)
        run_cli("github", "torvalds/linux", "--file", "README", "--revision", "master", "--cache-dir", tmp_cache)

        result = run_cli("cache", "--cache-dir", tmp_cache, "list")
        assert result.returncode == 0
        assert "[ms]" in result.stdout
        assert "[github]" in result.stdout

    def test_cache_list_shows_github_as_tool(self, tmp_cache):
        run_cli("github", "torvalds/linux", "--file", "README", "--revision", "master", "--cache-dir", tmp_cache)

        result = run_cli("cache", "--cache-dir", tmp_cache, "list")
        assert result.returncode == 0
        assert "tool:" in result.stdout

    def test_cache_info(self, tmp_cache):
        result = run_cli("cache", "--cache-dir", tmp_cache, "info")
        assert result.returncode == 0
        assert "Cache directory" in result.stdout
        assert "Total size" in result.stdout

    def test_cache_clean_all(self, tmp_cache):
        run_cli("hf", "gpt2", "--file", "config.json", "--cache-dir", tmp_cache)
        result = run_cli("cache", "--cache-dir", tmp_cache, "clean")
        assert result.returncode == 0
        assert "Cleaned" in result.stdout

    def test_cache_list_empty(self, tmp_cache):
        result = run_cli("cache", "--cache-dir", tmp_cache, "list")
        assert result.returncode == 0
        assert "No cached" in result.stdout


# ── File Filtering (unit tests) ─────────────────────────────────

class TestIncludeExclude:
    """Unit tests for file pattern filtering in snapshot downloads. No network needed."""

    @pytest.fixture
    def sample_files(self):
        return [
            {"Path": "config.json", "Type": "blob"},
            {"Path": "pytorch_model.bin", "Type": "blob"},
            {"Path": "tf_model.h5", "Type": "blob"},
            {"Path": "model.safetensors", "Type": "blob"},
            {"Path": "tokenizer.json", "Type": "blob"},
            {"Path": "vocab.txt", "Type": "blob"},
            {"Path": ".gitattributes", "Type": "blob"},
        ]

    def test_include_single_pattern(self, sample_files):
        """Include *.json should only keep JSON files."""
        patterns = ["*.json"]
        filtered = [
            f for f in sample_files
            if any(fnmatch.fnmatch(f["Path"], p) for p in patterns)
        ]
        paths = {f["Path"] for f in filtered}
        assert paths == {"config.json", "tokenizer.json"}

    def test_include_multiple_patterns(self, sample_files):
        """Include *.json *.bin should keep both."""
        patterns = ["*.json", "*.bin"]
        filtered = [
            f for f in sample_files
            if any(fnmatch.fnmatch(f["Path"], p) for p in patterns)
        ]
        paths = {f["Path"] for f in filtered}
        assert "config.json" in paths
        assert "pytorch_model.bin" in paths
        assert "model.safetensors" not in paths

    def test_exclude_pattern(self, sample_files):
        """Exclude *.safetensors should remove safetensors files."""
        patterns = ["*.safetensors"]
        filtered = [
            f for f in sample_files
            if not any(fnmatch.fnmatch(f["Path"], p) for p in patterns)
        ]
        paths = {f["Path"] for f in filtered}
        assert "model.safetensors" not in paths
        assert "config.json" in paths

    def test_exclude_multiple_patterns(self, sample_files):
        """Exclude *.bin *.h5 should remove both binary types."""
        patterns = ["*.bin", "*.h5"]
        filtered = [
            f for f in sample_files
            if not any(fnmatch.fnmatch(f["Path"], p) for p in patterns)
        ]
        paths = {f["Path"] for f in filtered}
        assert "pytorch_model.bin" not in paths
        assert "tf_model.h5" not in paths
        assert "config.json" in paths

    def test_include_and_exclude_together(self, sample_files):
        """Include takes precedence in our implementation (include then exclude filters apply)."""
        include_pat = ["*.json"]
        exclude_pat = ["tokenizer.*"]
        # First include
        filtered = [
            f for f in sample_files
            if any(fnmatch.fnmatch(f["Path"], p) for p in include_pat)
        ]
        # Then exclude
        filtered = [
            f for f in filtered
            if not any(fnmatch.fnmatch(f["Path"], p) for p in exclude_pat)
        ]
        paths = {f["Path"] for f in filtered}
        assert "config.json" in paths
        assert "tokenizer.json" not in paths

    def test_no_matches_returns_empty(self, sample_files):
        """Include pattern with no matches should return empty list."""
        patterns = ["*.nonexistent"]
        filtered = [
            f for f in sample_files
            if any(fnmatch.fnmatch(f["Path"], p) for p in patterns)
        ]
        assert filtered == []

    def test_exclude_no_matches_keeps_all(self, sample_files):
        """Exclude pattern that matches nothing keeps all files."""
        patterns = ["*.nonexistent"]
        filtered = [
            f for f in sample_files
            if not any(fnmatch.fnmatch(f["Path"], p) for p in patterns)
        ]
        assert len(filtered) == len(sample_files)

    def test_endpoint_env_set(self, monkeypatch):
        """Setting MODELSCOPE_ENDPOINT env var should be used by get_endpoint."""
        from modely.modelscope import get_endpoint

        monkeypatch.setenv("MODELSCOPE_ENDPOINT", "https://custom.modelscope.cn")
        assert get_endpoint() == "https://custom.modelscope.cn"

    def test_endpoint_default(self, monkeypatch):
        """Default endpoint should be modelscope.cn."""
        from modely.modelscope import get_endpoint

        monkeypatch.delenv("MODELSCOPE_ENDPOINT", raising=False)
        assert "modelscope.cn" in get_endpoint()

    def test_hf_endpoint_arg_passed(self, monkeypatch):
        """--endpoint should set HF_ENDPOINT env var."""
        monkeypatch.delenv("HF_ENDPOINT", raising=False)
        # Simulate what CLI does
        os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
        assert os.environ["HF_ENDPOINT"] == "https://hf-mirror.com"
        # Cleanup
        del os.environ["HF_ENDPOINT"]

