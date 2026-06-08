"""Manifest and lockfile helpers for modely-ai."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Iterable, List, Optional

from .files import filter_files, list_repo_files
from .get import download_resource
from .types import DownloadManifest, FileInfo
from .uri import parse_modely_uri


def sha256_file(path: str) -> str:
    """Compute a file's SHA256 digest."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_manifest(manifest: DownloadManifest, output: str) -> None:
    """Write a JSON manifest."""
    with open(output, "w") as f:
        json.dump(manifest.to_dict(), f, indent=2, ensure_ascii=False)


def read_manifest(path: str) -> DownloadManifest:
    """Read a JSON manifest or lockfile."""
    with open(path, "r") as f:
        data = json.load(f)
    files = [FileInfo(**item) for item in data.get("files", [])]
    return DownloadManifest(
        source=data["source"],
        repo_type=data["repo_type"],
        repo_id=data["repo_id"],
        revision=data.get("revision"),
        local_path=data.get("local_path"),
        files=files,
        include=data.get("include"),
        exclude=data.get("exclude"),
        metadata=data.get("metadata") or {},
    )


def create_lock(resource: str, *, revision=None, include=None, exclude=None, output="modely.lock", token=None) -> DownloadManifest:
    """Create a lockfile describing the selected remote files."""
    ref = parse_modely_uri(resource)
    if revision:
        ref.revision = revision
    files = filter_files(list_repo_files(ref, token=token), include, exclude)
    manifest = DownloadManifest(
        source=ref.source,
        repo_type=ref.repo_type,
        repo_id=ref.repo_id,
        revision=ref.revision,
        files=files,
        include=include,
        exclude=exclude,
        metadata={"kind": "lock"},
    )
    write_manifest(manifest, output)
    return manifest


def install_lock(lockfile: str, *, local_dir=None, cache_dir=None, token=None, force_download=False):
    """Install resources described by a lockfile."""
    manifest = read_manifest(lockfile)
    resource = _manifest_uri(manifest)
    path = download_resource(
        resource,
        revision=manifest.revision,
        cache_dir=cache_dir,
        local_dir=local_dir,
        token=token,
        include=manifest.include,
        exclude=manifest.exclude,
        force_download=force_download,
    )
    manifest.local_path = path
    return path


def create_download_manifest(resource: str, local_path: str, *, include=None, exclude=None, checksum=False, output=None):
    """Create a manifest for files present under local_path."""
    ref = parse_modely_uri(resource)
    files: List[FileInfo] = []
    root = Path(local_path)
    if root.is_file():
        files.append(FileInfo(path=root.name, size=root.stat().st_size, sha256=sha256_file(str(root)) if checksum else None))
    elif root.exists():
        for p in root.rglob("*"):
            if p.is_file() and ".git" not in p.parts:
                rel = str(p.relative_to(root))
                files.append(FileInfo(path=rel, size=p.stat().st_size, sha256=sha256_file(str(p)) if checksum else None))
    files = filter_files(files, include, exclude)
    manifest = DownloadManifest(ref.source, ref.repo_type, ref.repo_id, ref.revision, str(local_path), files, include, exclude)
    if output:
        write_manifest(manifest, output)
    return manifest


def _manifest_uri(manifest: DownloadManifest) -> str:
    if manifest.source == "github":
        return f"github://{manifest.repo_id}"
    return f"{manifest.source}://{manifest.repo_type}s/{manifest.repo_id}"
