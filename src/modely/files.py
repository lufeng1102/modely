"""Unified file listing and dry-run helpers."""

from __future__ import annotations

import fnmatch
import json
import sys
from typing import Iterable, List, Optional

from .auth import get_token
from .types import FileInfo, RepoRef
from .uri import parse_modely_uri


def format_file_size(size_bytes):
    """Format bytes into human-readable form."""
    if size_bytes is None or size_bytes == 0:
        return "-"
    if size_bytes >= 1_000_000_000:
        return f"{size_bytes / 1_000_000_000:.1f} GB"
    if size_bytes >= 1_000_000:
        return f"{size_bytes / 1_000_000:.1f} MB"
    if size_bytes >= 1_000:
        return f"{size_bytes / 1_000:.1f} KB"
    return f"{size_bytes} B"


def list_repo_files(ref_or_uri, *, revision=None, token=None, endpoint=None, release=None) -> List[FileInfo]:
    """List files for any supported source."""
    ref = ref_or_uri if isinstance(ref_or_uri, RepoRef) else parse_modely_uri(ref_or_uri)
    if revision:
        ref.revision = revision
    token = get_token(ref.source, token)
    if ref.source == "hf":
        from .hf import list_files
        return list_files(ref.repo_id, repo_type=ref.repo_type, revision=ref.revision or "main", token=token, endpoint=endpoint)
    if ref.source == "ms":
        from .modelscope import list_files
        return list_files(ref.repo_id, repo_type=ref.repo_type, revision=ref.revision, token=token)
    if ref.source == "github":
        from .github import github_list_files, github_release_assets
        if release:
            return github_release_assets(ref.repo_id, release=release, token=token)
        return github_list_files(ref.repo_id, revision=ref.revision or "main", token=token)
    raise ValueError(f"Unsupported source: {ref.source}")


def filter_files(files: Iterable[FileInfo], allow_patterns=None, ignore_patterns=None) -> List[FileInfo]:
    """Apply include/exclude glob filters to FileInfo objects."""
    filtered = [f for f in files if getattr(f, "type", "blob") != "tree"]
    if allow_patterns:
        filtered = [f for f in filtered if any(fnmatch.fnmatch(f.path, p) for p in allow_patterns)]
    if ignore_patterns:
        filtered = [f for f in filtered if not any(fnmatch.fnmatch(f.path, p) for p in ignore_patterns)]
    return filtered


def print_file_list(files, source, repo_id, *, as_json=False):
    """Print a formatted file list."""
    if as_json:
        print(json.dumps([_file_to_dict(f) for f in files], indent=2, ensure_ascii=False))
        return
    if not files:
        print(f"No files found in {repo_id}")
        return
    headers = ["Path", "Size", "Type"]
    rows = []
    col_widths = [len(h) for h in headers]
    for f in files:
        d = _file_to_dict(f)
        row = [d.get("path", "-"), format_file_size(d.get("size", 0)), d.get("type", "blob")]
        rows.append(row)
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(cell)))
    print(f"\n[{source.upper()}] {repo_id}\n")
    print("  ".join(h.ljust(w) for h, w in zip(headers, col_widths)))
    print("  ".join("-" * w for w in col_widths))
    for row in rows:
        path = str(row[0])
        if len(path) > 70:
            path = path[:67] + "..."
        print(f"{path.ljust(col_widths[0])}  {str(row[1]).ljust(col_widths[1])}  {str(row[2]).ljust(col_widths[2])}")
    print(f"\n{len(files)} file(s) shown.\n")


def do_dry_run(source, repo_id, repo_type, revision, allow_patterns, ignore_patterns, files):
    """Simulate a download and print a summary."""
    normalized = [_normalize_file(f) for f in files]
    blobs = [f for f in normalized if f.type != "tree"]
    filtered = filter_files(blobs, allow_patterns, ignore_patterns)
    total_size = sum(f.size or 0 for f in filtered)
    print(f"\n[{source.upper()}] {repo_id} (dry-run)")
    print(f"  Repository type: {repo_type}")
    print(f"  Revision:        {revision}")
    print(f"  Total files:     {len(blobs)}")
    if allow_patterns:
        print(f"  Include:         {' '.join(allow_patterns)}")
    if ignore_patterns:
        print(f"  Exclude:         {' '.join(ignore_patterns)}")
    print(f"  Would download:  {len(filtered)} file(s), {format_file_size(total_size)}")
    print()


def _normalize_file(value):
    if isinstance(value, FileInfo):
        return value
    return FileInfo(
        path=value.get("Path", value.get("path", "")),
        size=value.get("Size", value.get("size", 0)) or 0,
        type=value.get("Type", value.get("type", "blob")),
        sha256=value.get("Sha256", value.get("sha256")),
        download_url=value.get("download_url"),
        metadata=value,
    )


def _file_to_dict(value):
    return _normalize_file(value).to_dict()
