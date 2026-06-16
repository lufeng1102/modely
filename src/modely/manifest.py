"""Manifest and lockfile helpers for modely-ai."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

from .files import filter_files, list_repo_files
from .info import get_repo_info
from .get import download_resource
from .profiles import resolve_download_profile
from .reliability import sha256_file
from .types import DownloadManifest, FileInfo, RepoRef
from .uri import format_modely_uri, parse_modely_uri
try:
    from importlib.metadata import version
except ImportError:  # pragma: no cover
    version = None



def write_manifest(manifest: DownloadManifest, output: str) -> None:
    """Write a JSON manifest."""
    with open(output, "w") as f:
        json.dump(manifest.to_dict(), f, indent=2, ensure_ascii=False)


def read_manifest(path: str) -> DownloadManifest:
    """Read a JSON manifest or lockfile."""
    with open(path, "r") as f:
        data = json.load(f)
    files = [FileInfo(**item) for item in data.get("files", [])]
    metadata = migrate_lock_metadata(data.get("metadata") or {}, data)
    return DownloadManifest(
        source=data["source"],
        repo_type=data["repo_type"],
        repo_id=data["repo_id"],
        revision=data.get("revision"),
        local_path=data.get("local_path"),
        files=files,
        include=data.get("include"),
        exclude=data.get("exclude"),
        metadata=metadata,
    )


def create_lock(resource: str, *, revision=None, include=None, exclude=None, output="modely.lock", token=None,
                endpoint=None, profile=None, alternatives=None, strict: bool = False, require_checksums: bool = False) -> DownloadManifest:
    """Create a lockfile describing the selected remote files."""
    ref = parse_modely_uri(resource)
    if revision:
        ref.revision = revision
    include, exclude = resolve_download_profile(profile, include, exclude)
    requested_revision = ref.revision
    resolved_info = _resolved_info(ref, token=token, endpoint=endpoint)
    resolved_revision = resolved_info.get("resolved_revision") or ref.revision
    files = filter_files(list_repo_files(ref, token=token, endpoint=endpoint), include, exclude)
    summary = lock_summary(DownloadManifest(ref.source, ref.repo_type, ref.repo_id, ref.revision, files=files))
    if require_checksums and summary["missing_checksum_count"]:
        raise ValueError("Cannot create strict lock: missing SHA256 metadata for selected files")
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
            "schema_version": 3,
            "created_by": "modely-ai",
            "modely_version": _modely_version(),
            "resource": format_modely_uri(ref),
            "requested_revision": requested_revision,
            "resolved_revision": ref.revision,
            "strict": strict,
            "require_checksums": require_checksums,
            "profile": profile,
            "include": include,
            "exclude": exclude,
            "alternatives": _parse_alternatives(alternatives),
        },
    )
    manifest.metadata.update(lock_summary(manifest))
    manifest.metadata["checksum_coverage"] = (manifest.metadata["checksum_count"] / manifest.metadata["file_count"]) if manifest.metadata["file_count"] else 1.0
    manifest.metadata["floating_revision"] = (requested_revision in {None, "main", "master", "latest"}) and not (resolved_info.get("resolved_commit") or resolved_info.get("resolved_version"))
    if strict and manifest.metadata["floating_revision"]:
        raise ValueError("Cannot create strict lock for floating revision without a resolved commit/version")
    write_manifest(manifest, output)
    return manifest


def lock_summary(manifest: DownloadManifest) -> dict:
    """Return summary fields for a lock or manifest."""
    checksum_count = sum(1 for f in manifest.files if f.sha256)
    return {
        "file_count": len(manifest.files),
        "total_size": sum(f.size or 0 for f in manifest.files),
        "checksum_count": checksum_count,
        "missing_checksum_count": len(manifest.files) - checksum_count,
    }


def install_lock(lockfile: str, *, local_dir=None, cache_dir=None, token=None, force_download=False, fallback=False, prefer=None):
    """Install resources described by a lockfile."""
    manifest = read_manifest(lockfile)
    resource = _manifest_uri(manifest)
    alternatives = prefer or ",".join(manifest.metadata.get("alternatives") or [])
    path = download_resource(
        resource if not fallback else manifest.repo_id,
        source="auto" if fallback else manifest.source,
        repo_type=manifest.repo_type,
        revision=manifest.revision,
        cache_dir=cache_dir,
        local_dir=local_dir,
        token=token,
        include=manifest.include,
        exclude=manifest.exclude,
        prefer=alternatives or "default",
        fallback=fallback,
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


def validate_lock(lockfile: str, *, local_dir=None, checksum=False, require_checksums: bool = False, strict: bool = False) -> dict:
    """Validate a lockfile against local files without network access."""
    manifest = read_manifest(lockfile)
    root = Path(local_dir or manifest.local_path or ".")
    missing_files = []
    checksum_mismatches = []
    missing_checksums = []
    size_mismatches = []
    checked_files = 0
    for file_info in manifest.files:
        path = root / file_info.path
        if not path.exists():
            missing_files.append(file_info.path)
            continue
        checked_files += 1
        if file_info.size and path.stat().st_size != file_info.size:
            size_mismatches.append({"path": file_info.path, "expected": file_info.size, "actual": path.stat().st_size})
        if checksum or require_checksums or strict:
            if not file_info.sha256:
                missing_checksums.append(file_info.path)
            else:
                actual = sha256_file(str(path))
                if actual.lower() != file_info.sha256.lower():
                    checksum_mismatches.append({"path": file_info.path, "expected": file_info.sha256, "actual": actual})
    ok = not missing_files and not checksum_mismatches and not size_mismatches and not ((require_checksums or strict) and missing_checksums)
    return {
        "ok": ok,
        "lockfile": lockfile,
        "local_dir": str(root),
        "checked_files": checked_files,
        "total_files": len(manifest.files),
        "missing_files": missing_files,
        "checksum_mismatches": checksum_mismatches,
        "size_mismatches": size_mismatches,
        "missing_checksums": missing_checksums,
        "strict": strict,
        "require_checksums": require_checksums,
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
    if result.get("size_mismatches"):
        print("Size mismatches:")
        for item in result["size_mismatches"]:
            print(f"  - {item['path']}: expected {item['expected']}, got {item['actual']}")
    if result["missing_checksums"]:
        print("Missing checksums:")
        for path in result["missing_checksums"]:
            print(f"  - {path}")


def migrate_lock_metadata(metadata: dict, data: dict | None = None) -> dict:
    """Normalize older lock metadata to the current in-memory shape."""
    data = data or {}
    migrated = dict(metadata or {})
    migrated.setdefault("schema_version", migrated.get("schema_version", 1))
    migrated.setdefault("kind", "lock" if "files" in data else "manifest")
    migrated.setdefault("resource", None)
    migrated.setdefault("requested_revision", data.get("revision"))
    migrated.setdefault("resolved_revision", data.get("revision"))
    migrated.setdefault("resolved_commit", None)
    migrated.setdefault("resolved_version", None)
    migrated.setdefault("alternatives", [])
    migrated.setdefault("alternative_uris", [])
    return migrated


def _resolved_info(ref: RepoRef, *, token=None, endpoint=None) -> dict:
    try:
        info = get_repo_info(ref, token=token, endpoint=endpoint)
    except Exception:
        return {}
    metadata = info.metadata or {}
    resolved = info.revision or ref.revision
    commit = metadata.get("sha") or metadata.get("commit") or metadata.get("commit_hash") or metadata.get("revision")
    version_value = metadata.get("version") or metadata.get("datasetVersion")
    return {"resolved_revision": resolved, "resolved_commit": commit, "resolved_version": version_value}


def _alternative_uris(ref: RepoRef, alternatives, revision) -> list[str]:
    uris = []
    for item in _parse_alternatives(alternatives):
        if "://" in item:
            uris.append(item)
            continue
        try:
            uris.append(format_modely_uri(RepoRef(item, ref.repo_type, ref.repo_id, revision)))
        except Exception:
            continue
    return uris


def _parse_alternatives(alternatives) -> list[str]:
    if not alternatives:
        return []
    if isinstance(alternatives, str):
        return [item.strip() for item in alternatives.split(",") if item.strip()]
    return [str(item).strip() for item in alternatives if str(item).strip()]


def _manifest_uri(manifest: DownloadManifest) -> str:
    return format_modely_uri(RepoRef(manifest.source, manifest.repo_type, manifest.repo_id, manifest.revision))


def _modely_version() -> str:
    if version is None:
        return "unknown"
    try:
        return version("modely-ai")
    except Exception:
        return "unknown"
