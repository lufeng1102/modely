"""Shared dataclasses for modely-ai aggregation APIs."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RepoRef:
    """A normalized reference to a remote repository or file."""

    source: str
    repo_type: str
    repo_id: str
    revision: Optional[str] = None
    path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FileInfo:
    """Unified file metadata across supported sources."""

    path: str
    size: int = 0
    type: str = "blob"
    sha256: Optional[str] = None
    download_url: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RepoInfo:
    """Unified repository metadata across supported sources."""

    source: str
    repo_type: str
    repo_id: str
    url: str = ""
    author: Optional[str] = None
    revision: Optional[str] = None
    private: Optional[bool] = None
    downloads: int = 0
    likes: int = 0
    forks: int = 0
    created_at: Optional[str] = None
    last_modified: Optional[str] = None
    description: Optional[str] = None
    license: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DownloadManifest:
    """Manifest describing a concrete download or lockfile selection."""

    source: str
    repo_type: str
    repo_id: str
    revision: Optional[str] = None
    local_path: Optional[str] = None
    files: List[FileInfo] = field(default_factory=list)
    include: Optional[List[str]] = None
    exclude: Optional[List[str]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["files"] = [f.to_dict() if isinstance(f, FileInfo) else f for f in self.files]
        return data
