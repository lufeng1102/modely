"""Batch search and download helpers for modely-ai."""

from __future__ import annotations

import json
from typing import Iterable, Optional, Sequence

from .get import download_resource
from .search import SearchResult, search


def filter_results_by_tags(results: Iterable[SearchResult], tags: Sequence[str]) -> list[SearchResult]:
    """Return results whose tags contain all requested tags, case-insensitively."""
    required = _normalize_tags(tags)
    filtered: list[SearchResult] = []
    for result in results:
        available = {str(tag).strip().lower() for tag in (result.tags or []) if str(tag).strip()}
        if required.issubset(available):
            filtered.append(result)
    return filtered


def create_batch_download_plan(
    keyword: Optional[str] = None,
    *,
    source: str = "all",
    repo_type: str = "model",
    tags: Sequence[str],
    limit: int = 20,
    search_limit: Optional[int] = None,
    task: Optional[str] = None,
    library: Optional[str] = None,
    license: Optional[str] = None,
    sort: str = "downloads",
    direction: str = "desc",
    author: Optional[str] = None,
    after: Optional[str] = None,
    before: Optional[str] = None,
    full: bool = False,
) -> dict:
    """Create a dry-run batch download plan from tag-filtered search results."""
    required_tags = sorted(_normalize_tags(tags, required=False))
    if not required_tags and not _has_structured_filter(keyword=keyword, task=task, library=library, license=license, author=author, after=after, before=before):
        raise ValueError("at least one tag or search filter is required")
    fetched = search(
        keyword=keyword,
        source=source,
        repo_type=repo_type,
        task=task,
        library=library,
        license=license,
        sort=sort,
        direction=direction,
        limit=search_limit or limit,
        author=author,
        after=after,
        before=before,
        full=full,
    )
    matched = filter_results_by_tags(fetched, required_tags) if required_tags else list(fetched)
    if repo_type in {"model", "dataset"}:
        matched = [result for result in matched if result.repo_type == repo_type]
    selected = matched[:limit]
    return {
        "dry_run": True,
        "keyword": keyword,
        "source": source,
        "repo_type": repo_type,
        "tags": required_tags,
        "search_count": len(fetched),
        "matched_count": len(matched),
        "selected_count": len(selected),
        "candidates": [_result_to_dict(result) for result in matched],
        "downloads": [_download_item(result) for result in selected],
    }


def run_batch_download(
    plan: dict,
    *,
    local_dir: Optional[str] = None,
    cache_dir: Optional[str] = None,
    token: Optional[str] = None,
    include: Optional[list[str]] = None,
    exclude: Optional[list[str]] = None,
    profile: Optional[str] = None,
    prefer: str = "ms,hf,github",
    fallback: bool = False,
    force_download: bool = False,
    backend: str = "auto",
    with_lfs: bool = False,
    endpoint: Optional[str] = None,
    max_workers: Optional[int] = None,
    timeout: Optional[float] = None,
    retries: Optional[int] = None,
    checksum: bool = False,
    resume: bool = True,
    fail_fast: bool = False,
) -> dict:
    """Execute a batch download plan and return per-resource results."""
    results = []
    for item in plan.get("downloads", []):
        resource = item["resource"]
        try:
            path = download_resource(
                resource,
                cache_dir=cache_dir,
                local_dir=local_dir,
                token=token,
                include=include,
                exclude=exclude,
                prefer=prefer,
                fallback=fallback,
                force_download=force_download,
                backend=backend,
                with_lfs=with_lfs,
                profile=profile,
                endpoint=endpoint,
                max_workers=max_workers,
                timeout=timeout,
                retries=retries,
                checksum=checksum,
                resume=resume,
            )
            results.append({**item, "ok": True, "path": path, "error": None})
        except Exception as exc:
            results.append({**item, "ok": False, "path": None, "error": str(exc)})
            if fail_fast:
                break
    failed = sum(1 for item in results if not item["ok"])
    summary = {"total": len(results), "succeeded": len(results) - failed, "failed": failed}
    return {"ok": failed == 0, "dry_run": False, "plan": plan, "results": results, "summary": summary}


def print_batch_download_result(result: dict, *, as_json: bool = False) -> None:
    """Print a dry-run plan or execution result."""
    if as_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return
    if result.get("dry_run"):
        print(f"Matched:  {result.get('matched_count', 0)}")
        print(f"Selected: {result.get('selected_count', 0)}")
        if not result.get("downloads"):
            print("No resources matched the requested tags.")
        else:
            print("Resources to download (dry-run):")
            for item in result["downloads"]:
                print(f"  - {item['resource']}")
            print("Run again with --yes to download these resources.")
        return
    summary = result.get("summary") or {}
    print(f"Downloaded: {summary.get('succeeded', 0)}/{summary.get('total', 0)}")
    if summary.get("failed", 0):
        print("Failures:")
        for item in result.get("results") or []:
            if not item.get("ok"):
                print(f"  - {item.get('resource')}: {item.get('error')}")


def _normalize_tags(tags: Optional[Sequence[str]], *, required: bool = True) -> set[str]:
    normalized = {str(tag).strip().lower() for tag in (tags or []) if str(tag).strip()}
    if required and not normalized:
        raise ValueError("at least one tag is required")
    return normalized


def _has_structured_filter(**filters) -> bool:
    return any(value for value in filters.values())


def _download_item(result: SearchResult) -> dict:
    return {"resource": result.modely_uri, "id": result.id, "source": result.source, "repo_type": result.repo_type, "tags": result.tags}


def _result_to_dict(result: SearchResult) -> dict:
    return result.to_dict()
