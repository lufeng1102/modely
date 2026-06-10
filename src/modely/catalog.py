"""Local and cache asset catalog helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .common import cache
from .files import format_file_size
from .manifest import lock_summary, read_manifest
from .types import CatalogEntry, CatalogReport
from .uri import format_modely_uri

_MANIFEST_CANDIDATES = ("modely.lock", "modely-manifest.json")


def scan_catalog(
    root: Optional[str] = None,
    *,
    cache_dir: Optional[str] = None,
    from_cache: bool = False,
    include_scores: bool = False,
    include_scan: bool = False,
    use_remote: bool = False,
    token: Optional[str] = None,
    endpoint: Optional[str] = None,
) -> CatalogReport:
    """Scan a local directory or modely cache into a catalog report."""
    warnings = []
    if from_cache:
        entries = catalog_from_cache(cache_dir)
        report_root = cache.get_cache_dir(cache_dir)
        mode = "cache"
    else:
        scan_root = root or "."
        entries = catalog_from_directory(scan_root)
        report_root = str(Path(scan_root).resolve())
        mode = "directory"

    if (include_scores or include_scan) and not use_remote:
        warnings.append("score/scan enrichment skipped; pass --remote to allow metadata calls")
    elif use_remote and (include_scores or include_scan):
        _enrich_entries(entries, include_scores=include_scores, include_scan=include_scan, token=token, endpoint=endpoint, warnings=warnings)

    return CatalogReport(
        root=report_root,
        entries=entries,
        summary=catalog_summary(entries),
        warnings=warnings,
        metadata={"mode": mode, "remote": use_remote},
    )


def catalog_from_cache(cache_dir: Optional[str] = None) -> list[CatalogEntry]:
    """Return catalog entries from the modely cache."""
    entries = []
    for item in cache.list_cache(cache_dir=cache_dir, detail=True):
        file_count = len(item.get("files") or [])
        entry = CatalogEntry(
            id=f"{item.get('source')}:{item.get('repo_type')}:{item.get('repo_id')}:{item.get('revision')}",
            source=item.get("source"),
            repo_type=item.get("repo_type"),
            repo_id=item.get("repo_id"),
            revision=item.get("revision"),
            local_path=item.get("path", ""),
            size=item.get("size", 0) or 0,
            file_count=file_count,
            metadata={"origin": "cache", "size_str": item.get("size_str"), "files": item.get("files", [])},
        )
        entries.append(entry)
    return entries


def catalog_from_directory(root: str) -> list[CatalogEntry]:
    """Return catalog entries from a local directory root."""
    root_path = Path(root).expanduser().resolve()
    if not root_path.exists():
        return []
    candidates = [root_path] if _looks_like_asset_dir(root_path) else [p for p in sorted(root_path.iterdir()) if p.is_dir()]
    entries = []
    for path in candidates:
        entry = _entry_from_directory(path)
        if entry:
            entries.append(entry)
    return entries


def find_manifest_file(path: Path) -> Optional[Path]:
    """Find a modely lock or manifest file in a local asset directory."""
    for name in _MANIFEST_CANDIDATES:
        candidate = path / name
        if candidate.exists() and candidate.is_file():
            return candidate
    matches = sorted([p for p in path.glob("*.lock") if p.is_file()] + [p for p in path.glob("*manifest*.json") if p.is_file()])
    return matches[0] if matches else None


def catalog_summary(entries: list[CatalogEntry]) -> dict:
    """Return aggregate summary for catalog entries."""
    by_source = {}
    by_repo_type = {}
    for entry in entries:
        by_source[entry.source or "unknown"] = by_source.get(entry.source or "unknown", 0) + 1
        by_repo_type[entry.repo_type or "unknown"] = by_repo_type.get(entry.repo_type or "unknown", 0) + 1
    return {
        "total_entries": len(entries),
        "total_size": sum(e.size or 0 for e in entries),
        "by_source": by_source,
        "by_repo_type": by_repo_type,
        "with_lock": sum(1 for e in entries if e.lock_path),
        "with_manifest": sum(1 for e in entries if e.manifest_path),
        "with_score": sum(1 for e in entries if e.score),
        "with_scan": sum(1 for e in entries if e.scan),
    }


def print_catalog_report(report: CatalogReport, *, as_json: bool = False) -> None:
    """Print a catalog report."""
    if as_json:
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
        return
    print(f"Root:          {report.root}")
    print(f"Total entries: {report.summary.get('total_entries', 0)}")
    print(f"Total size:    {format_file_size(report.summary.get('total_size', 0))}")
    if not report.entries:
        print("No catalog entries found.")
    else:
        print("Entries:")
        for entry in report.entries:
            label = entry.repo_id or entry.id
            print(f"  - {label} [{entry.source or 'unknown'}:{entry.repo_type or 'unknown'}] {format_file_size(entry.size)}")
            print(f"    Path: {entry.local_path}")
    if report.warnings:
        print("Warnings:")
        for warning in report.warnings:
            print(f"  - {warning}")


def write_catalog_report(report: CatalogReport, output: str) -> None:
    """Write a catalog report to JSON."""
    with open(output, "w") as f:
        json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)


def _entry_from_directory(path: Path) -> Optional[CatalogEntry]:
    files = [p for p in path.rglob("*") if p.is_file() and ".git" not in p.parts]
    if not files:
        return None
    size = sum(p.stat().st_size for p in files)
    manifest_path = find_manifest_file(path)
    manifest = None
    if manifest_path:
        try:
            manifest = read_manifest(str(manifest_path))
        except Exception:
            manifest = None
    if manifest:
        summary = lock_summary(manifest)
        is_lock = manifest_path.name.endswith(".lock") or manifest.metadata.get("kind") == "lock"
        return CatalogEntry(
            id=f"{manifest.source}:{manifest.repo_type}:{manifest.repo_id}:{manifest.revision or 'unknown'}",
            source=manifest.source,
            repo_type=manifest.repo_type,
            repo_id=manifest.repo_id,
            revision=manifest.revision,
            local_path=str(path),
            size=summary["total_size"] or size,
            file_count=summary["file_count"] or len(files),
            manifest_path=None if is_lock else str(manifest_path),
            lock_path=str(manifest_path) if is_lock else None,
            metadata={"origin": "directory", "manifest_metadata": manifest.metadata},
        )
    return CatalogEntry(
        id=path.name,
        local_path=str(path),
        size=size,
        file_count=len(files),
        metadata={"origin": "directory"},
    )


def _looks_like_asset_dir(path: Path) -> bool:
    if find_manifest_file(path):
        return True
    names = {p.name.lower() for p in path.iterdir() if p.is_file()}
    return bool(names & {"config.json", "tokenizer.json", "README.md", "readme.md"})


def _entry_uri(entry: CatalogEntry) -> Optional[str]:
    if not entry.source or not entry.repo_type or not entry.repo_id:
        return None
    try:
        return format_modely_uri(entry)
    except Exception:
        return None


def _enrich_entries(entries, *, include_scores, include_scan, token, endpoint, warnings) -> None:
    if include_scores:
        from .score import score_resource
    if include_scan:
        from .scan import scan_resource
    for entry in entries:
        uri = _entry_uri(entry)
        if not uri:
            warnings.append(f"skipped remote enrichment for {entry.id}: missing source/repo metadata")
            continue
        try:
            if include_scores:
                score = score_resource(uri, revision=entry.revision, token=token, endpoint=endpoint)
                entry.score = {"score": score.score, "grade": score.grade, "breakdown": score.breakdown.to_dict(), "risks": score.risks}
            if include_scan:
                scan = scan_resource(uri, revision=entry.revision, token=token, endpoint=endpoint)
                entry.scan = {"risk_level": scan.risk_level, "summary": scan.summary, "finding_ids": [f.id for f in scan.findings]}
        except Exception as exc:
            warnings.append(f"remote enrichment failed for {entry.id}: {exc}")
