"""Manifest and lockfile helpers for modely-ai."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

from .files import filter_files, list_repo_files
from .get import download_resource
from .reliability import sha256_file
from .types import DownloadManifest, FileInfo
from .uri import format_modely_uri, parse_modely_uri



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
        metadata={
            "kind": "lock",
            "schema_version": 1,
            "created_by": "modely-ai",
            "file_count": len(files),
            "total_size": sum(f.size or 0 for f in files),
        },
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
    manifest = DownloadManifest(ref.source, ref.repo_type, ref.repo_id, ref.revision, str(local_path), files, include, exclude,
                                metadata={"kind": "manifest", "schema_version": 1, "file_count": len(files), "total_size": sum(f.size or 0 for f in files)})
    if output:
        write_manifest(manifest, output)
    return manifest


def validate_lock(lockfile: str, *, local_dir=None, checksum=False) -> dict:
    """Validate a lockfile against local files without network access."""
    manifest = read_manifest(lockfile)
    root = Path(local_dir or manifest.local_path or ".")
    missing_files = []
    checksum_mismatches = []
    missing_checksums = []
    checked_files = 0
    for file_info in manifest.files:
        path = root / file_info.path
        if not path.exists():
            missing_files.append(file_info.path)
            continue
        checked_files += 1
        if checksum:
            if not file_info.sha256:
                missing_checksums.append(file_info.path)
            else:
                actual = sha256_file(str(path))
                if actual.lower() != file_info.sha256.lower():
                    checksum_mismatches.append({"path": file_info.path, "expected": file_info.sha256, "actual": actual})
    ok = not missing_files and not checksum_mismatches
    return {
        "ok": ok,
        "lockfile": lockfile,
        "local_dir": str(root),
        "checked_files": checked_files,
        "total_files": len(manifest.files),
        "missing_files": missing_files,
        "checksum_mismatches": checksum_mismatches,
        "missing_checksums": missing_checksums,
    }


def print_lock_validation(result: dict, *, as_json=False) -> None:
    """Print lock validation results."""
    if as_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return
    print(f"Lockfile:      {result['lockfile']}")
    print(f"Local dir:     {result['local_dir']}")
    print(f"Status:        {'ok' if result['ok'] else 'failed'}")
    print(f"Checked files: {result['checked_files']}/{result['total_files']}")
    if result["missing_files"]:
        print("Missing files:")
        for path in result["missing_files"]:
            print(f"  - {path}")
    if result["checksum_mismatches"]:
        print("Checksum mismatches:")
        for item in result["checksum_mismatches"]:
            print(f"  - {item['path']}")
    if result["missing_checksums"]:
        print("Missing checksums:")
        for path in result["missing_checksums"]:
            print(f"  - {path}")


def _manifest_uri(manifest: DownloadManifest) -> str:
    return format_modely_uri(manifest)
