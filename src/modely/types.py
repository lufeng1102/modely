"""Shared dataclasses for modely-ai aggregation APIs."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


class _DataclassDictMixin:
    """Provide a JSON-ready dictionary representation for dataclasses."""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class RepoRef(_DataclassDictMixin):
    """A normalized reference to a remote repository or file."""

    source: str
    repo_type: str
    repo_id: str
    revision: Optional[str] = None
    path: Optional[str] = None

@dataclass
class FileInfo(_DataclassDictMixin):
    """Unified file metadata across supported sources."""

    path: str
    size: int = 0
    type: str = "blob"
    sha256: Optional[str] = None
    download_url: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class RepoInfo(_DataclassDictMixin):
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

@dataclass
class FileSummary(_DataclassDictMixin):
    """Summary of a file selection."""

    total_files: int = 0
    total_size: int = 0
    selected_files: int = 0
    selected_size: int = 0
    categories: Dict[str, int] = field(default_factory=dict)
    category_sizes: Dict[str, int] = field(default_factory=dict)

@dataclass
class DownloadPlan(_DataclassDictMixin):
    """A dry-run plan describing what a download would select."""

    source: str
    repo_type: str
    repo_id: str
    revision: Optional[str] = None
    include: Optional[List[str]] = None
    exclude: Optional[List[str]] = None
    profile: Optional[str] = None
    files: List[FileInfo] = field(default_factory=list)
    summary: Optional[FileSummary] = None
    cache_dir: Optional[str] = None
    local_dir: Optional[str] = None
    cache_hits: int = 0
    cache_misses: int = 0
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SourceProfile(_DataclassDictMixin):
    """A source endpoint profile used for probing and routing."""

    name: str
    source: str
    endpoint: str
    description: str = ""
    builtin: bool = True

@dataclass
class ProbeResult(_DataclassDictMixin):
    """Result of probing a source profile."""

    profile: str
    source: str
    endpoint: str
    ok: bool
    latency_ms: int = 0
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class AssetCard(_DataclassDictMixin):
    """Best-effort model/dataset/repository card content."""

    source: str
    repo_type: str
    repo_id: str
    revision: Optional[str] = None
    path: Optional[str] = None
    text: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class AssetAnalysis(_DataclassDictMixin):
    """Analysis of a model/dataset/repository asset."""

    info: RepoInfo
    summary: FileSummary
    files: List[FileInfo] = field(default_factory=list)
    largest_files: List[FileInfo] = field(default_factory=list)
    weight_formats: Dict[str, int] = field(default_factory=dict)
    has_config: bool = False
    has_tokenizer: bool = False
    has_card: bool = False
    card: Optional[AssetCard] = None
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ComparisonResult(_DataclassDictMixin):
    """Comparison between two analyzed assets."""

    left: AssetAnalysis
    right: AssetAnalysis
    same_license: bool = False
    shared_tags: List[str] = field(default_factory=list)
    different_tags: Dict[str, List[str]] = field(default_factory=dict)
    size_delta: int = 0
    file_count_delta: int = 0
    summary: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

@dataclass
class BenchmarkResult(_DataclassDictMixin):
    """Endpoint or small-file benchmark result."""

    profile: str
    source: str
    endpoint: str
    ok: bool
    latency_ms: int = 0
    throughput_bps: int = 0
    bytes_read: int = 0
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class BackendCapability(_DataclassDictMixin):
    """Capability declaration for a download/query backend."""

    name: str
    source: str
    kind: str
    available: bool = True
    requires_extra: Optional[str] = None
    supports: Dict[str, bool] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)

@dataclass
class AssetDiff(_DataclassDictMixin):
    """Change-oriented diff between two analyzed assets."""

    left: AssetAnalysis
    right: AssetAnalysis
    added_files: List[str] = field(default_factory=list)
    removed_files: List[str] = field(default_factory=list)
    common_files: int = 0
    license_changed: bool = False
    tag_changes: Dict[str, List[str]] = field(default_factory=dict)
    size_delta: int = 0
    file_count_delta: int = 0
    category_delta: Dict[str, int] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

@dataclass
class DownloadManifest(_DataclassDictMixin):
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
