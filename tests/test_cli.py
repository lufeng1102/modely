"""Integration tests for modely CLI and download functions.

These tests require network access and are marked with pytest.mark.integration.
Run with: pytest tests/ -m integration
Skip with: pytest tests/ -m "not integration"
"""

import os
import shutil
import subprocess

import pytest

from modely.common import cache as cache_mod


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
