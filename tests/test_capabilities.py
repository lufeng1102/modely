"""Unit tests for backend capability reporting."""

from modely.backends import get_backend_capabilities, list_backends


def test_list_backends_includes_core_sources():
    sources = {item.source for item in list_backends()}
    assert {"hf", "ms", "github", "kaggle"}.issubset(sources)


def test_get_backend_capabilities_accepts_alias():
    capability = get_backend_capabilities("hf")
    assert capability.name == "hf-sdk"
    assert capability.supports["single_file"] is True
    assert capability.supports["snapshot"] is True
