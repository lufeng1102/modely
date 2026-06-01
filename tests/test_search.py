"""Unit and integration tests for the search module."""

import json
import types
from datetime import datetime, timezone

import pytest

import modely  # noqa: ensure package is imported before submodule access
import modely.search.hf_search as hf_mod
import modely.search.ms_search as ms_mod
from modely.search import SearchResult, search, main as search_main
from modely.search.display import format_table, format_json, _format_count, _format_date


# ── Helpers ─────────────────────────────────────────────────────

def _mock_model_info(**overrides):
    """Create a fake ModelInfo / DatasetInfo object via SimpleNamespace."""
    defaults = {
        "id": "test-org/test-model",
        "author": "test-org",
        "downloads": 1_000_000,
        "likes": 500,
        "last_modified": datetime(2024, 6, 1, tzinfo=timezone.utc),
        "created_at": datetime(2023, 1, 15, tzinfo=timezone.utc),
        "pipeline_tag": "text-classification",
        "library_name": "transformers",
        "tags": ["pytorch", "bert"],
        "license": "mit",
        "description": "A test model",
    }
    defaults.update(overrides)
    return types.SimpleNamespace(**defaults)


# ── SearchResult dataclass ──────────────────────────────────────

class TestSearchResult:
    def test_defaults(self):
        r = SearchResult(id="a/b", source="hf", repo_type="model")
        assert r.downloads == 0
        assert r.likes == 0
        assert r.tags == []

    def test_full_fields(self):
        r = SearchResult(
            id="a/b",
            source="hf",
            repo_type="model",
            author="author1",
            downloads=100,
            likes=10,
            last_modified="2024-01-01",
            created_at="2023-01-01",
            pipeline_tag="text-generation",
            library_name="transformers",
            tags=["tag1"],
            license="mit",
            description="desc",
        )
        assert r.author == "author1"
        assert r.downloads == 100


# ── Display ─────────────────────────────────────────────────────

class TestFormatCount:
    def test_millions(self):
        assert _format_count(5_200_000) == "5.2M"

    def test_thousands(self):
        assert _format_count(1_500) == "1.5K"

    def test_small(self):
        assert _format_count(42) == "42"

    def test_zero(self):
        assert _format_count(0) == "0"


class TestFormatDate:
    def test_iso(self):
        assert _format_date("2024-06-01T12:00:00+00:00") == "2024-06-01"

    def test_none(self):
        assert _format_date(None) == "-"

    def test_short(self):
        assert _format_date("2024-06-01") == "2024-06-01"


class TestFormatTable:
    def test_empty(self):
        assert format_table([]) == "No results found."

    def test_single_result(self):
        r = SearchResult(id="org/model", source="hf", repo_type="model",
                         pipeline_tag="text-gen", downloads=1000, likes=50,
                         last_modified="2024-06-01")
        output = format_table([r])
        assert "org/model" in output
        assert "HF" in output
        assert "text-gen" in output
        assert "1.0K" in output

    def test_result_count_shown(self):
        r = SearchResult(id="a/b", source="hf", repo_type="model")
        output = format_table([r])
        assert "1 result(s) shown" in output

    def test_long_id_truncated(self):
        r = SearchResult(id="x" * 60, source="hf", repo_type="model")
        output = format_table([r])
        assert "..." in output


class TestFormatJson:
    def test_valid_json(self):
        r = SearchResult(id="a/b", source="hf", repo_type="model")
        j = format_json([r])
        parsed = json.loads(j)
        assert parsed[0]["id"] == "a/b"
        assert parsed[0]["source"] == "hf"

    def test_empty(self):
        assert format_json([]) == "[]"


# ── HF Search (unit) ────────────────────────────────────────────

class TestHuggingFaceSearch:
    def test_returns_list_of_search_results(self, monkeypatch):
        fake_info = _mock_model_info()

        def mock_list_models(self, **kwargs):
            return [fake_info]

        monkeypatch.setattr(hf_mod.HfApi, "list_models", mock_list_models)

        results = hf_mod.search_huggingface("test", repo_type="model")
        assert len(results) == 1
        assert isinstance(results[0], SearchResult)
        assert results[0].id == "test-org/test-model"
        assert results[0].source == "hf"

    def test_dataset_repo_type(self, monkeypatch):
        fake_info = _mock_model_info(id="org/dataset", pipeline_tag=None)

        def mock_list_datasets(self, **kwargs):
            return [fake_info]

        monkeypatch.setattr(hf_mod.HfApi, "list_datasets", mock_list_datasets)

        results = hf_mod.search_huggingface("test", repo_type="dataset")
        assert len(results) == 1
        assert results[0].id == "org/dataset"

    def test_empty_results(self, monkeypatch):
        def mock_list_models(self, **kwargs):
            return []

        monkeypatch.setattr(hf_mod.HfApi, "list_models", mock_list_models)

        results = hf_mod.search_huggingface("no-match")
        assert results == []

    def test_error_handled_gracefully(self, monkeypatch):
        def mock_list_models(self, **kwargs):
            raise RuntimeError("API down")

        monkeypatch.setattr(hf_mod.HfApi, "list_models", mock_list_models)

        results = hf_mod.search_huggingface("test")
        assert results == []

    def test_maps_datetime_fields(self, monkeypatch):
        dt = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        fake_info = _mock_model_info(last_modified=dt, created_at=dt)

        def mock_list_models(self, **kwargs):
            return [fake_info]

        monkeypatch.setattr(hf_mod.HfApi, "list_models", mock_list_models)

        results = hf_mod.search_huggingface("test")
        assert results[0].last_modified == "2025-01-15T12:00:00+00:00"
        assert results[0].created_at == "2025-01-15T12:00:00+00:00"

    def test_maps_tags_list(self, monkeypatch):
        fake_info = _mock_model_info(tags=["tag-a", "tag-b"])

        def mock_list_models(self, **kwargs):
            return [fake_info]

        monkeypatch.setattr(hf_mod.HfApi, "list_models", mock_list_models)

        results = hf_mod.search_huggingface("test")
        assert "tag-a" in results[0].tags
        assert "tag-b" in results[0].tags


# ── MS Search (unit) ────────────────────────────────────────────

class TestModelScopeSearch:
    def test_returns_list_of_search_results(self, monkeypatch):
        class FakeResponse:
            def json(self):
                return {
                    "Data": {
                        "Model": {
                            "Models": [
                                {
                                    "Path": "owner",
                                    "Name": "test-model",
                                    "Organization": "owner",
                                    "Downloads": 500,
                                    "Stars": 10,
                                    "CreatedTime": 1700000000,
                                    "LastUpdatedTime": 1717200000,
                                    "Tasks": [{"Name": "text-generation"}],
                                    "Tags": [{"Name": "nlp"}],
                                    "License": "mit",
                                    "Description": "A test model",
                                }
                            ],
                            "TotalCount": 1,
                        }
                    }
                }

            def raise_for_status(self):
                pass

        monkeypatch.setattr(ms_mod.requests, "put",
            lambda url, json, timeout, headers: FakeResponse())

        results = ms_mod.search_modelscope("test", repo_type="model")
        assert len(results) == 1
        assert isinstance(results[0], SearchResult)
        assert results[0].id == "owner/test-model"
        assert results[0].source == "ms"
        assert results[0].pipeline_tag == "text-generation"

    def test_dataset_returns_empty(self, monkeypatch):
        """Dataset search is not yet supported for ModelScope; should return []."""
        results = ms_mod.search_modelscope("test", repo_type="dataset")
        assert results == []

    def test_timeout_handled(self, monkeypatch):
        def mock_put(**kwargs):
            raise ms_mod.requests.exceptions.Timeout()

        monkeypatch.setattr(ms_mod.requests, "put", mock_put)

        results = ms_mod.search_modelscope("test")
        assert results == []

    def test_connection_error_handled(self, monkeypatch):
        def mock_put(**kwargs):
            raise ms_mod.requests.exceptions.ConnectionError()

        monkeypatch.setattr(ms_mod.requests, "put", mock_put)

        results = ms_mod.search_modelscope("test")
        assert results == []

    def test_empty_response(self, monkeypatch):
        class FakeResponse:
            def json(self):
                return {}

            def raise_for_status(self):
                pass

        monkeypatch.setattr(ms_mod.requests, "put",
            lambda url, json, timeout, headers: FakeResponse())

        results = ms_mod.search_modelscope("test")
        assert results == []


# ── Orchestrator ────────────────────────────────────────────────

class TestSearchOrchestrator:
    def test_source_hf_only(self, monkeypatch):
        fake_info = _mock_model_info()

        def mock_list_models(self, **kwargs):
            return [fake_info]

        monkeypatch.setattr(hf_mod.HfApi, "list_models", mock_list_models)

        results = search("gpt2", source="hf")
        assert len(results) == 1
        assert results[0].source == "hf"

    def test_source_ms_only(self, monkeypatch):
        class FakeResponse:
            def json(self):
                return {
                    "Data": {
                        "Model": {
                            "Models": [
                                {
                                    "Path": "a",
                                    "Name": "b",
                                    "Downloads": 100,
                                    "Stars": 5,
                                    "Tasks": [],
                                    "Tags": [],
                                }
                            ],
                            "TotalCount": 1,
                        }
                    }
                }

            def raise_for_status(self):
                pass

        monkeypatch.setattr(ms_mod.requests, "put",
            lambda url, json, timeout, headers: FakeResponse())

        results = search("gpt2", source="ms")
        assert len(results) == 1
        assert results[0].source == "ms"

    def test_date_filter_applied(self, monkeypatch):
        old = _mock_model_info(id="old-model", last_modified=datetime(2022, 1, 1, tzinfo=timezone.utc))
        new = _mock_model_info(id="new-model", last_modified=datetime(2024, 6, 1, tzinfo=timezone.utc))

        def mock_list_models(self, **kwargs):
            return [old, new]

        monkeypatch.setattr(hf_mod.HfApi, "list_models", mock_list_models)

        results = search("test", source="hf", after="2023-01-01")
        ids = [r.id for r in results]
        assert "new-model" in ids
        assert "old-model" not in ids

    def test_sort_desc_downloads(self, monkeypatch):
        low = _mock_model_info(id="low", downloads=100)
        high = _mock_model_info(id="high", downloads=10000)

        def mock_list_models(self, **kwargs):
            return [low, high]

        monkeypatch.setattr(hf_mod.HfApi, "list_models", mock_list_models)

        results = search("test", source="hf", sort="downloads", direction="desc")
        assert results[0].id == "high"
        assert results[1].id == "low"

    def test_unknown_source_raises(self):
        with pytest.raises(ValueError, match="Unknown source"):
            search("test", source="bad")


# ── CLI main ────────────────────────────────────────────────────

class TestSearchMain:
    def test_outputs_table_by_default(self, monkeypatch, capsys):
        fake_info = _mock_model_info()

        def mock_list_models(self, **kwargs):
            return [fake_info]

        monkeypatch.setattr(hf_mod.HfApi, "list_models", mock_list_models)

        args = types.SimpleNamespace(
            keyword="test",
            source="hf",
            repo_type="model",
            task=None,
            library=None,
            license=None,
            sort="downloads",
            direction="desc",
            limit=20,
            author=None,
            after=None,
            before=None,
            full=False,
            json=False,
        )
        search_main(args)
        out = capsys.readouterr().out
        assert "test-org/test-model" in out
        assert "1 result(s) shown" in out

    def test_json_output(self, monkeypatch, capsys):
        fake_info = _mock_model_info()

        def mock_list_models(self, **kwargs):
            return [fake_info]

        monkeypatch.setattr(hf_mod.HfApi, "list_models", mock_list_models)

        args = types.SimpleNamespace(
            keyword="test",
            source="hf",
            repo_type="model",
            task=None,
            library=None,
            license=None,
            sort="downloads",
            direction="desc",
            limit=20,
            author=None,
            after=None,
            before=None,
            full=False,
            json=True,
        )
        search_main(args)
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert parsed[0]["id"] == "test-org/test-model"

    def test_backend_error_shows_empty_results(self, monkeypatch, capsys):
        """When the backend raises, search_main gracefully shows no results."""
        def mock_list_models(self, **kwargs):
            raise RuntimeError("boom")

        monkeypatch.setattr(hf_mod.HfApi, "list_models", mock_list_models)

        args = types.SimpleNamespace(
            keyword="test",
            source="hf",
            repo_type="model",
            task=None,
            library=None,
            license=None,
            sort="downloads",
            direction="desc",
            limit=20,
            author=None,
            after=None,
            before=None,
            full=False,
            json=False,
        )
        search_main(args)
        out = capsys.readouterr().out
        # Should gracefully show no results, not crash
        assert "No results found" in out


# ── CLI Integration (subprocess) ────────────────────────────────

@pytest.mark.integration
class TestSearchIntegration:
    def test_hf_search_returns_results(self):
        """Real search against Hugging Face should return at least one result."""
        import subprocess
        result = subprocess.run(
            ["modely-ai", "search", "gpt2", "--source", "hf", "--limit", "3"],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0
        assert "gpt2" in result.stdout.lower() or "result" in result.stdout.lower()

    def test_json_output_valid(self):
        """JSON output should be parseable and non-empty."""
        import subprocess
        result = subprocess.run(
            ["modely-ai", "search", "gpt2", "--source", "hf", "--limit", "2", "--json"],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0
        parsed = json.loads(result.stdout)
        assert isinstance(parsed, list)
        assert len(parsed) > 0
        assert "id" in parsed[0]

    def test_dataset_search(self):
        """Search for datasets."""
        import subprocess
        result = subprocess.run(
            ["modely-ai", "search", "glue", "--source", "hf", "--repo-type", "dataset", "--limit", "3", "--json"],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0
        parsed = json.loads(result.stdout)
        assert isinstance(parsed, list)

    def test_ms_search_returns_results(self):
        """Real search against ModelScope should not crash."""
        import subprocess
        result = subprocess.run(
            ["modely-ai", "search", "qwen", "--source", "ms", "--limit", "3", "--json"],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0
        json.loads(result.stdout)
