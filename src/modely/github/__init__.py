#!/usr/bin/env python
"""
A module to download files and repositories from GitHub.
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Union
from urllib.parse import quote

import requests
from tqdm import tqdm

from modely.common import cache as github_cache


def github_file_download(
    repo_id: str,
    filename: str,
    *,
    revision: str = "main",
    cache_dir: Optional[Union[str, Path]] = None,
    local_dir: Optional[str] = None,
    token: Optional[str] = None,
    force_download: bool = False,
) -> str:
    """
    Download a single file from a GitHub repository.

    Args:
        repo_id: Repository ID in the format "owner/repo"
        filename: Path to the file in the repository
        revision: Branch, tag, or commit SHA (default: main)
        cache_dir: Directory to cache downloaded files
        local_dir: Local directory to save the file
        token: GitHub personal access token for private repos
        force_download: Force re-download even if file exists

    Returns:
        Path to the downloaded file
    """
    # Check cache first
    if not force_download:
        cached = github_cache.is_cached(
            repo_id, filename, revision, "model", "github", cache_dir
        )
        if cached:
            file_path = github_cache.get_file_path(
                repo_id, filename, revision, "model", "github", cache_dir
            )
            print(f"File already cached at: {file_path}")
            return file_path

    # Determine save location
    if local_dir:
        file_path = os.path.join(local_dir, filename)
        os.makedirs(local_dir, exist_ok=True)
    else:
        file_path = github_cache.get_file_path(
            repo_id, filename, revision, "model", "github", cache_dir
        )
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

    # Build raw URL
    encoded_path = quote(filename, safe="/")
    url = f"https://raw.githubusercontent.com/{repo_id}/{revision}/{encoded_path}"

    # Download with requests
    headers = {}
    if token:
        headers["Authorization"] = f"token {token}"

    try:
        response = requests.get(url, headers=headers, stream=True, timeout=30)
        response.raise_for_status()

        total_size = int(response.headers.get("content-length", 0))
        with open(file_path, "wb") as f:
            if total_size > 0:
                with tqdm(
                    total=total_size, unit="B", unit_scale=True, desc=filename
                ) as pbar:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            pbar.update(len(chunk))
            else:
                f.write(response.content)

        return file_path
    except requests.HTTPError as e:
        if response.status_code == 404:
            raise Exception(
                f"File not found: {filename} in {repo_id} (revision: {revision})"
            )
        raise Exception(f"Failed to download {filename}: {e}")
    except Exception as e:
        raise Exception(f"Failed to download {filename}: {e}")


def github_clone(
    repo_id: str,
    *,
    revision: str = "main",
    cache_dir: Optional[Union[str, Path]] = None,
    local_dir: Optional[str] = None,
    token: Optional[str] = None,
    with_lfs: bool = False,
    force_download: bool = False,
) -> str:
    """
    Clone a GitHub repository using git.

    Args:
        repo_id: Repository ID in the format "owner/repo"
        revision: Branch, tag, or commit SHA (default: main)
        cache_dir: Directory to cache downloaded files
        local_dir: Local directory to clone the repository
        token: GitHub personal access token for private repos
        with_lfs: Enable Git LFS support for large files
        force_download: Force re-clone even if cached

    Returns:
        Path to the cloned repository
    """
    # Check cache first
    if not force_download:
        cached_path = github_cache.get_cached_repo_path(
            repo_id, "model", revision, "github", cache_dir
        )
        if cached_path and os.path.exists(os.path.join(cached_path, ".git")):
            print(f"Repository already cached at: {cached_path}")
            return cached_path

    # Determine target directory
    if local_dir:
        target_dir = local_dir
    else:
        target_dir = github_cache.get_repo_cache_dir(
            repo_id, "model", revision, "github", cache_dir
        )

    # Build git URL with optional token authentication
    if token:
        git_url = f"https://{token}@github.com/{repo_id}.git"
    else:
        git_url = f"https://github.com/{repo_id}.git"

    # Remove existing directory if force download
    if force_download and os.path.exists(target_dir):
        shutil.rmtree(target_dir)

    # Clone the repository
    os.makedirs(target_dir, exist_ok=True)
    parent_dir = os.path.dirname(target_dir)
    repo_name = os.path.basename(target_dir)

    cmd = [
        "git",
        "clone",
        "--depth",
        "1",
        "--branch",
        revision,
        git_url,
        repo_name,
    ]

    try:
        print(f"Cloning {repo_id} (revision: {revision})...")
        result = subprocess.run(
            cmd,
            cwd=parent_dir,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            # Try without depth if branch/tag doesn't support shallow clone
            if "--depth" in cmd:
                cmd.remove("--depth")
                cmd.remove("1")
                result = subprocess.run(
                    cmd,
                    cwd=parent_dir,
                    capture_output=True,
                    text=True,
                )
            if result.returncode != 0:
                raise Exception(f"Git clone failed: {result.stderr}")

        # Git LFS support
        if with_lfs:
            lfs_result = subprocess.run(
                ["git", "lfs", "pull"],
                cwd=target_dir,
                capture_output=True,
                text=True,
            )
            if lfs_result.returncode != 0:
                print(f"Warning: Git LFS pull failed: {lfs_result.stderr}")

        return target_dir
    except FileNotFoundError:
        raise Exception(
            "git command not found. Please install git to use this feature."
        )
    except Exception as e:
        raise Exception(f"Failed to clone repository: {e}")


# Alias for consistency with hf/ms modules
snapshot_download = github_clone


def main():
    """Main function to handle command-line arguments for GitHub downloads."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Download from GitHub"
    )
    parser.add_argument(
        "repo_id", type=str, help="Repository ID in format owner/repo"
    )
    parser.add_argument(
        "--file",
        type=str,
        help="Specific file to download from the repository",
    )
    parser.add_argument(
        "--revision",
        type=str,
        default="main",
        help="Branch, tag, or commit SHA (default: main)",
    )
    parser.add_argument(
        "--cache-dir",
        type=str,
        default=None,
        help="Cache directory for downloaded files",
    )
    parser.add_argument(
        "--local-dir",
        type=str,
        default=None,
        help="Local directory to download files to",
    )
    parser.add_argument(
        "--token",
        type=str,
        default=None,
        help="GitHub personal access token for private repositories",
    )
    parser.add_argument(
        "--with-lfs",
        action="store_true",
        help="Enable Git LFS support for large files",
    )
    parser.add_argument(
        "--force-download",
        action="store_true",
        help="Force re-download even if file exists",
    )

    args = parser.parse_args()

    try:
        if args.file:
            result = github_file_download(
                repo_id=args.repo_id,
                filename=args.file,
                revision=args.revision,
                cache_dir=args.cache_dir,
                local_dir=args.local_dir,
                token=args.token,
                force_download=args.force_download,
            )
            print(f"Successfully downloaded file to: {result}")
        else:
            result = github_clone(
                repo_id=args.repo_id,
                revision=args.revision,
                cache_dir=args.cache_dir,
                local_dir=args.local_dir,
                token=args.token,
                with_lfs=args.with_lfs,
                force_download=args.force_download,
            )
            print(f"Repository cloned to: {result}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
