"""Shared download reliability helpers."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Callable, Optional, TypeVar

T = TypeVar("T")


@dataclass
class DownloadOptions:
    """Normalized reliability options for download backends."""

    retries: int = 3
    timeout: Optional[float] = None
    checksum: bool = False
    resume: bool = True
    max_workers: Optional[int] = None


def normalize_download_options(
    *,
    retries: Optional[int] = None,
    timeout: Optional[float] = None,
    checksum: bool = False,
    resume: bool = True,
    max_workers: Optional[int] = None,
) -> DownloadOptions:
    """Validate and normalize download reliability options."""
    retries = 3 if retries is None else retries
    if retries < 0:
        raise ValueError("retries must be >= 0")
    if timeout is not None and timeout <= 0:
        raise ValueError("timeout must be > 0")
    if max_workers is not None and max_workers <= 0:
        raise ValueError("max_workers must be > 0")
    return DownloadOptions(retries=retries, timeout=timeout, checksum=checksum, resume=resume, max_workers=max_workers)


def retry_call(fn: Callable[[], T], *, retries: int = 3, label: str = "operation") -> T:
    """Call a function with simple exponential-backoff retries."""
    attempts = retries + 1
    last_error = None
    for attempt in range(attempts):
        try:
            return fn()
        except Exception as exc:  # noqa: PERF203 - intentional retry boundary
            last_error = exc
            if attempt >= retries:
                break
            time.sleep(min(2 ** attempt, 8) * 0.1)
    raise Exception(f"{label} failed after {attempts} attempt(s): {last_error}") from last_error


def diagnose_download_error(source: str, exc: Exception) -> str:
    """Return a user-facing diagnostic hint for common download failures."""
    text = str(exc)
    lower = text.lower()
    hints = []
    if "401" in lower or "unauthorized" in lower:
        hints.append("authentication failed; check token or login state")
    if "403" in lower or "forbidden" in lower:
        hints.append("access forbidden; private/gated resources may require permission or license acceptance")
    if "404" in lower or "not found" in lower:
        hints.append("resource, file, or revision was not found")
    if "timeout" in lower or "timed out" in lower:
        hints.append("network timeout; try increasing --timeout or using --fallback")
    if "rate limit" in lower or "429" in lower:
        hints.append("rate limited; retry later or use an authenticated token")
    if not hints:
        hints.append("see backend error for details")
    return f"{source}: {text} ({'; '.join(hints)})"


def sha256_file(path: str) -> str:
    """Compute a file SHA256 digest."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_sha256(path: str, expected: str) -> bool:
    """Return whether a file SHA256 digest matches the expected value."""
    return sha256_file(path).lower() == expected.lower()
