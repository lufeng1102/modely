"""Unified download entrypoint for modely-ai."""

from __future__ import annotations

from typing import List, Optional

from .auth import get_token
from .profiles import resolve_download_profile
from .reliability import diagnose_download_error, normalize_download_options, retry_call
from .types import RepoRef
from .uri import normalize_repo_type, normalize_source, parse_modely_uri


def download_resource(
    resource: str,
    *,
    source: str = "auto",
    repo_type: str = "model",
    revision: Optional[str] = None,
    file: Optional[str] = None,
    cache_dir: Optional[str] = None,
    local_dir: Optional[str] = None,
    token: Optional[str] = None,
    include: Optional[List[str]] = None,
    exclude: Optional[List[str]] = None,
    prefer: str = "ms,hf,github",
    fallback: bool = False,
    force_download: bool = False,
    backend: str = "auto",
    with_lfs: bool = False,
    profile: Optional[str] = None,
    endpoint: Optional[str] = None,
    max_workers: Optional[int] = None,
    timeout: Optional[float] = None,
    retries: Optional[int] = None,
    checksum: bool = False,
    resume: bool = True,
):
    """Download a resource by URI, explicit source, or auto/fallback source order."""
    include, exclude = resolve_download_profile(profile, include, exclude)
    options = normalize_download_options(
        retries=retries,
        timeout=timeout,
        checksum=checksum,
        resume=resume,
        max_workers=max_workers,
    )

    if "://" in resource:
        ref = parse_modely_uri(resource)
        if revision:
            ref.revision = revision
        if file:
            ref.path = file
        return _download_ref(ref, cache_dir=cache_dir, local_dir=local_dir, token=token,
                             include=include, exclude=exclude, force_download=force_download,
                             backend=backend, with_lfs=with_lfs, endpoint=endpoint,
                             options=options)

    if source != "auto":
        ref = RepoRef(normalize_source(source), normalize_repo_type(repo_type, source), resource, revision, file)
        return _download_ref(ref, cache_dir=cache_dir, local_dir=local_dir, token=token,
                             include=include, exclude=exclude, force_download=force_download,
                             backend=backend, with_lfs=with_lfs, endpoint=endpoint,
                             options=options)

    if source == "auto" and prefer == "fastest":
        from .sources import rank_sources
        ranked = [r.source for r in rank_sources(resource, candidates=["hf", "hf-mirror", "ms", "github"], timeout=options.timeout or 5) if r.ok]
        seen = set()
        prefer = ",".join(s for s in ranked if not (s in seen or seen.add(s))) or "ms,hf,github"

    errors = []
    for src in [s.strip() for s in prefer.split(",") if s.strip()]:
        try:
            ref = RepoRef(normalize_source(src), normalize_repo_type(repo_type, src), resource, revision, file)
            return _download_ref(ref, cache_dir=cache_dir, local_dir=local_dir, token=token,
                                 include=include, exclude=exclude, force_download=force_download,
                                 backend=backend, with_lfs=with_lfs, endpoint=endpoint,
                                 options=options)
        except Exception as exc:
            errors.append(diagnose_download_error(src, exc))
            if not fallback:
                raise
    raise Exception("All sources failed: " + "; ".join(errors))


def _download_ref(ref: RepoRef, *, cache_dir=None, local_dir=None, token=None, include=None, exclude=None,
                  force_download=False, backend="auto", with_lfs=False, endpoint=None,
                  options=None):
    options = options or normalize_download_options()
    token = get_token(ref.source, token)
    if ref.source == "hf":
        from .hf import hf_file_download, snapshot_download
        if ref.path:
            return retry_call(
                lambda: hf_file_download(ref.repo_id, ref.path, repo_type=ref.repo_type, revision=ref.revision or "main",
                                         cache_dir=cache_dir, local_dir=local_dir, token=token,
                                         force_download=force_download, resume_download=options.resume),
                retries=options.retries,
                label=f"hf:{ref.repo_id}/{ref.path}",
            )
        return retry_call(
            lambda: snapshot_download(ref.repo_id, repo_type=ref.repo_type, revision=ref.revision or "main",
                                      cache_dir=cache_dir, local_dir=local_dir, token=token,
                                      allow_patterns=include, ignore_patterns=exclude,
                                      force_download=force_download, max_workers=options.max_workers),
            retries=options.retries,
            label=f"hf:{ref.repo_id}",
        )
    if ref.source == "ms":
        from .modelscope import dataset_file_download, model_file_download, snapshot_download
        if ref.path:
            if ref.repo_type == "dataset":
                return retry_call(
                    lambda: dataset_file_download(ref.repo_id, ref.path, revision=ref.revision, cache_dir=cache_dir,
                                                  local_dir=local_dir, token=token, backend=backend),
                    retries=options.retries,
                    label=f"ms:{ref.repo_id}/{ref.path}",
                )
            return retry_call(
                lambda: model_file_download(ref.repo_id, ref.path, revision=ref.revision, cache_dir=cache_dir,
                                            local_dir=local_dir, token=token, backend=backend),
                retries=options.retries,
                label=f"ms:{ref.repo_id}/{ref.path}",
            )
        return retry_call(
            lambda: snapshot_download(ref.repo_id, repo_type=ref.repo_type, revision=ref.revision, cache_dir=cache_dir,
                                      local_dir=local_dir, token=token, force_download=force_download,
                                      allow_patterns=include, ignore_patterns=exclude, backend=backend),
            retries=options.retries,
            label=f"ms:{ref.repo_id}",
        )
    if ref.source == "github":
        from .github import github_file_download, github_clone
        if ref.path:
            return retry_call(
                lambda: github_file_download(ref.repo_id, ref.path, revision=ref.revision or "main", cache_dir=cache_dir,
                                             local_dir=local_dir, token=token, force_download=force_download,
                                             timeout=options.timeout),
                retries=options.retries,
                label=f"github:{ref.repo_id}/{ref.path}",
            )
        return retry_call(
            lambda: github_clone(ref.repo_id, revision=ref.revision or "main", cache_dir=cache_dir, local_dir=local_dir,
                                 token=token, with_lfs=with_lfs, force_download=force_download,
                                 allow_patterns=include, ignore_patterns=exclude),
            retries=options.retries,
            label=f"github:{ref.repo_id}",
        )
    if ref.source == "kaggle":
        from .kaggle import kaggle_download
        return retry_call(
            lambda: kaggle_download(ref.repo_id, repo_type=ref.repo_type, file=ref.path,
                                    local_dir=local_dir, cache_dir=cache_dir, force_download=force_download),
            retries=options.retries,
            label=f"kaggle:{ref.repo_id}",
        )
    raise ValueError(f"Unsupported source: {ref.source}")
