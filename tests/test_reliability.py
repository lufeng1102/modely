"""Unit tests for shared download reliability helpers."""

import pytest

from modely.reliability import diagnose_download_error, normalize_download_options, retry_call


def test_normalize_download_options_validates_values():
    with pytest.raises(ValueError):
        normalize_download_options(retries=-1)
    with pytest.raises(ValueError):
        normalize_download_options(timeout=0)
    with pytest.raises(ValueError):
        normalize_download_options(max_workers=0)


def test_retry_call_retries_until_success():
    calls = {"count": 0}

    def flaky():
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("temporary")
        return "ok"

    assert retry_call(flaky, retries=1, label="flaky") == "ok"
    assert calls["count"] == 2


def test_diagnose_download_error_adds_auth_hint():
    message = diagnose_download_error("hf", Exception("401 Unauthorized"))
    assert "authentication failed" in message
