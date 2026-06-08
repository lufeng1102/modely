"""Unified repository info helpers."""

from __future__ import annotations

import json
from typing import Optional

from .auth import get_token
from .types import RepoInfo, RepoRef
from .uri import parse_modely_uri


def get_repo_info(ref_or_uri, *, revision: Optional[str] = None, token: Optional[str] = None, endpoint: Optional[str] = None) -> RepoInfo:
    """Return best-effort repository metadata for any supported source."""
    ref = ref_or_uri if isinstance(ref_or_uri, RepoRef) else parse_modely_uri(ref_or_uri)
    if revision:
        ref.revision = revision
    token = get_token(ref.source, token)
    if ref.source == "hf":
        from .hf import get_repo_info as hf_info
        return hf_info(ref.repo_id, repo_type=ref.repo_type, revision=ref.revision or "main", token=token, endpoint=endpoint)
    if ref.source == "ms":
        from .modelscope import get_repo_info as ms_info
        return ms_info(ref.repo_id, repo_type=ref.repo_type, revision=ref.revision, token=token)
    if ref.source == "github":
        from .github import github_repo_info
        return github_repo_info(ref.repo_id, revision=ref.revision or "main", token=token)
    raise ValueError(f"Unsupported source: {ref.source}")


def print_repo_info(info: RepoInfo, *, as_json: bool = False) -> None:
    """Print repository info as table-ish output or JSON."""
    if as_json:
        print(json.dumps(info.to_dict(), indent=2, ensure_ascii=False))
        return
    print(f"Source:        {info.source}")
    print(f"Repo type:     {info.repo_type}")
    print(f"Repo ID:       {info.repo_id}")
    if info.revision:
        print(f"Revision:      {info.revision}")
    if info.url:
        print(f"URL:           {info.url}")
    if info.author:
        print(f"Author:        {info.author}")
    if info.description:
        print(f"Description:   {info.description}")
    if info.license:
        print(f"License:       {info.license}")
    print(f"Downloads:     {info.downloads}")
    print(f"Likes/Stars:   {info.likes}")
    if info.forks:
        print(f"Forks:         {info.forks}")
    if info.last_modified:
        print(f"Last modified: {info.last_modified}")
    if info.created_at:
        print(f"Created at:    {info.created_at}")
    if info.tags:
        print(f"Tags:          {', '.join(info.tags[:20])}")
