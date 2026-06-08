"""Download-only sync/mirror helpers."""

from __future__ import annotations

from .get import download_resource
from .manifest import create_download_manifest


def sync_resource(resource: str, *, local_dir: str, revision=None, include=None, exclude=None,
                  token=None, cache_dir=None, manifest=None, checksum=False, force_download=False,
                  source="auto", prefer="ms,hf,github"):
    """Ensure a remote resource is materialized locally. No upload is performed."""
    path = download_resource(
        resource,
        source=source,
        revision=revision,
        local_dir=local_dir,
        cache_dir=cache_dir,
        token=token,
        include=include,
        exclude=exclude,
        prefer=prefer,
        fallback=True,
        force_download=force_download,
    )
    if manifest:
        create_download_manifest(resource if "://" in resource else f"hf://models/{resource}", path,
                                 include=include, exclude=exclude, checksum=checksum, output=manifest)
    return path
