"""URI parsing helpers for modely-ai resources."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from .types import RepoRef

_SUPPORTED_SOURCES = {"hf", "ms", "github", "kaggle"}
_REPO_TYPE_ALIASES = {
    "model": "model",
    "models": "model",
    "dataset": "dataset",
    "datasets": "dataset",
    "space": "space",
    "spaces": "space",
    "tool": "tool",
    "tools": "tool",
    "repo": "tool",
    "repos": "tool",
    "competition": "competition",
    "competitions": "competition",
}
_DEFAULT_REPO_TYPE = {
    "hf": "model",
    "ms": "model",
    "github": "tool",
    "kaggle": "dataset",
}


def normalize_source(source: str) -> str:
    """Normalize a source name."""
    if source == "modelscope":
        source = "ms"
    if source == "kg":
        source = "kaggle"
    if source not in _SUPPORTED_SOURCES:
        raise ValueError(f"Unsupported source: {source}")
    return source


def normalize_repo_type(repo_type: str | None, source: str = "hf") -> str:
    """Normalize repo type aliases such as models -> model."""
    if repo_type is None:
        return _DEFAULT_REPO_TYPE[normalize_source(source)]
    normalized = _REPO_TYPE_ALIASES.get(repo_type)
    if normalized is None:
        raise ValueError(f"Unsupported repo type: {repo_type}")
    if source == "github" and normalized not in {"tool"}:
        return "tool"
    return normalized


def parse_modely_uri(value: str, *, source: str | None = None, repo_type: str | None = None) -> RepoRef:
    """Parse a modely resource URI or a plain repo id into a RepoRef.

    Supported URI forms include::

        hf://models/gpt2
        hf://datasets/google/fleurs?revision=main&file=README.md
        ms://models/owner/name
        github://owner/repo

    Plain repo ids require an explicit source or default to Hugging Face.
    """
    parsed = urlparse(value)

    if parsed.scheme:
        src = normalize_source(parsed.scheme)
        parts = [p for p in parsed.path.split("/") if p]
        if src == "github":
            if parsed.netloc:
                repo_id = "/".join([parsed.netloc, *parts[:1]])
                extra = parts[1:]
            else:
                repo_id = "/".join(parts[:2])
                extra = parts[2:]
            rtype = "tool"
        elif src == "kaggle":
            if not parsed.netloc:
                raise ValueError(f"Missing repo type in URI: {value}")
            rtype = normalize_repo_type(parsed.netloc, src)
            repo_id = "/".join(parts[:2]) if rtype == "dataset" else "/".join(parts[:1])
            extra = parts[2:] if rtype == "dataset" else parts[1:]
        else:
            if not parsed.netloc:
                raise ValueError(f"Missing repo type in URI: {value}")
            rtype = normalize_repo_type(parsed.netloc, src)
            repo_id = "/".join(parts)
            extra = []
        query = parse_qs(parsed.query)
        revision = _first(query.get("revision"))
        file_path = _first(query.get("file")) or _first(query.get("path"))
        if extra and not file_path:
            file_path = "/".join(extra)
        if not repo_id or ((src in {"ms", "github"} or (src == "kaggle" and rtype == "dataset")) and "/" not in repo_id):
            raise ValueError(f"Invalid repository id in URI: {value}")
        return RepoRef(source=src, repo_type=rtype, repo_id=repo_id, revision=revision, path=file_path)

    src = normalize_source(source or "hf")
    return RepoRef(
        source=src,
        repo_type=normalize_repo_type(repo_type, src),
        repo_id=value,
    )


def format_modely_uri(ref: RepoRef) -> str:
    """Format a RepoRef as a modely URI."""
    if ref.source == "github":
        uri = f"github://{ref.repo_id}"
    elif ref.source == "kaggle":
        uri = f"kaggle://{ref.repo_type}s/{ref.repo_id}"
    else:
        uri = f"{ref.source}://{ref.repo_type}s/{ref.repo_id}"
    query = []
    if ref.revision:
        query.append(f"revision={ref.revision}")
    if ref.path:
        query.append(f"file={ref.path}")
    return uri + (("?" + "&".join(query)) if query else "")


def _first(values):
    if not values:
        return None
    return values[0]
