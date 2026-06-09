"""Backend capability registry."""

from __future__ import annotations

import importlib.util
import json

from .types import BackendCapability

_FEATURES = ["single_file", "snapshot", "resume", "retries", "timeout", "max_workers", "range_requests", "checksum", "auth", "mirror", "search", "info", "files"]


def _supports(**kwargs):
    return {name: bool(kwargs.get(name, False)) for name in _FEATURES}


_BACKENDS = {
    "hf-sdk": BackendCapability("hf-sdk", "hf", "official-sdk", supports=_supports(single_file=True, snapshot=True, resume=True, retries=True, timeout=True, max_workers=True, checksum=True, auth=True, mirror=True, search=True, info=True, files=True)),
    "hf-xet": BackendCapability("hf-xet", "hf", "transport", available=importlib.util.find_spec("hf_xet") is not None, requires_extra="hf_xet", supports=_supports(snapshot=True, resume=True, retries=True, max_workers=True, auth=True, mirror=True), notes=["Optional high-performance Hugging Face transport when installed/configured."]),
    "modelscope-official": BackendCapability("modelscope-official", "ms", "official-sdk", available=importlib.util.find_spec("modelscope") is not None, requires_extra="modelscope", supports=_supports(single_file=True, snapshot=True, resume=True, retries=True, timeout=True, auth=True, search=True, info=True, files=True)),
    "modelscope-lightweight": BackendCapability("modelscope-lightweight", "ms", "http", supports=_supports(single_file=True, snapshot=True, resume=True, retries=True, timeout=True, range_requests=True, checksum=True, auth=True, mirror=True, info=True, files=True)),
    "github-git": BackendCapability("github-git", "github", "git", supports=_supports(snapshot=True, retries=True, auth=True, files=True, info=True), notes=["Git clone backend; timeout/max-worker controls are limited."]),
    "github-http": BackendCapability("github-http", "github", "http", supports=_supports(single_file=True, retries=True, timeout=True, auth=True, info=True, files=True)),
    "kaggle-api": BackendCapability("kaggle-api", "kaggle", "official-api", available=importlib.util.find_spec("kaggle") is not None, requires_extra="kaggle", supports=_supports(single_file=True, snapshot=True, retries=True, auth=True, search=True, info=True, files=True)),
    "generic-http": BackendCapability("generic-http", "http", "http", available=False, supports=_supports(single_file=True, resume=True, retries=True, timeout=True, range_requests=True, checksum=True), notes=["Declared for future generic URL support; not wired as a first-class source yet."]),
}

_ALIASES = {"hf": "hf-sdk", "ms": "modelscope-lightweight", "modelscope": "modelscope-lightweight", "github": "github-git", "kaggle": "kaggle-api"}


def list_backends() -> list[BackendCapability]:
    """List known backend capabilities."""
    return list(_BACKENDS.values())


def get_backend_capabilities(name: str) -> BackendCapability:
    """Return capabilities for a backend name or alias."""
    key = _ALIASES.get(name, name)
    if key not in _BACKENDS:
        raise ValueError(f"Unknown backend: {name}")
    return _BACKENDS[key]


def print_backend_capabilities(items, *, as_json: bool = False) -> None:
    """Print one or more backend capability records."""
    if not isinstance(items, list):
        items = [items]
    if as_json:
        print(json.dumps([i.to_dict() for i in items], indent=2, ensure_ascii=False))
        return
    for item in items:
        status = "available" if item.available else "unavailable"
        extra = f" (extra: {item.requires_extra})" if item.requires_extra else ""
        print(f"{item.name:24} {item.source:8} {item.kind:14} {status}{extra}")
        supported = [k for k, v in item.supports.items() if v]
        print(f"  supports: {', '.join(supported) if supported else '-'}")
        for note in item.notes:
            print(f"  note: {note}")
