"""Authentication helpers for modely-ai."""

from __future__ import annotations

import os
from typing import Optional

from .common import cache
from .uri import normalize_source

_ENV_TOKENS = {
    "hf": ("HF_TOKEN", "HUGGINGFACE_TOKEN"),
    "ms": ("MODELSCOPE_TOKEN",),
    "github": ("GITHUB_TOKEN",),
}


def get_token(source: str, explicit_token: Optional[str] = None) -> Optional[str]:
    """Resolve a token with CLI > environment > config priority."""
    source = normalize_source(source)
    if explicit_token:
        return explicit_token
    for name in _ENV_TOKENS[source]:
        value = os.environ.get(name)
        if value:
            return value
    return (_load_tokens()).get(source)


def save_token(source: str, token: str) -> None:
    """Persist a source token in ~/.modely/config.json."""
    source = normalize_source(source)
    config = cache._load_config()
    tokens = dict(config.get("tokens") or {})
    tokens[source] = token
    config["tokens"] = tokens
    cache._save_config(config)


def delete_token(source: str) -> bool:
    """Delete a persisted token. Returns True if one existed."""
    source = normalize_source(source)
    config = cache._load_config()
    tokens = dict(config.get("tokens") or {})
    existed = source in tokens
    tokens.pop(source, None)
    config["tokens"] = tokens
    cache._save_config(config)
    return existed


def has_token(source: str) -> bool:
    return bool(get_token(source))


def _load_tokens():
    return cache._load_config().get("tokens") or {}


def whoami(source: str, token: Optional[str] = None) -> str:
    """Return a best-effort identity string for a source token."""
    source = normalize_source(source)
    token = get_token(source, token)
    if not token:
        return "No token configured"
    if source == "hf":
        try:
            from huggingface_hub import HfApi
            info = HfApi(token=token).whoami(token=token)
            return info.get("name") or info.get("fullname") or "Authenticated"
        except Exception:
            return "Authenticated token configured"
    if source == "github":
        try:
            import requests
            r = requests.get("https://api.github.com/user", headers={"Authorization": f"Bearer {token}", "User-Agent": "modely-ai"}, timeout=15)
            r.raise_for_status()
            return r.json().get("login") or "Authenticated"
        except Exception:
            return "Authenticated token configured"
    return "Authenticated token configured"
