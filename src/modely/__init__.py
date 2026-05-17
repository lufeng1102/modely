import sys
import argparse
from .modelscope import (
    main as modelscope_main,
    model_file_download,
    dataset_file_download,
    snapshot_download as modelscope_snapshot_download,
    HubApi
)
from .hf import (
    hf_file_download,
    snapshot_download as hf_snapshot_download,
    main as hf_main
)
from .github import (
    github_file_download,
    snapshot_download as github_snapshot_download,
    main as github_main
)
from .common import cache


def main():
    parser = argparse.ArgumentParser(prog="modely", description="Modely - A tool for downloading models from various sources")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ModelScope subcommand (renamed to "ms")
    ms_parser = subparsers.add_parser("ms", help="Download models from ModelScope")
    ms_parser.add_argument('repo_id', type=str, help='Repository ID in format owner/name')
    ms_parser.add_argument('--file', type=str, help='Specific file path to download from the repository')
    ms_parser.add_argument('--repo-type', choices=['model', 'dataset'], default='model', help='Type of repository (default: model)')
    ms_parser.add_argument('--revision', type=str, default=None, help='Revision of the model (default: master)')
    ms_parser.add_argument('--cache-dir', type=str, default=None, help='Cache directory for downloaded files')
    ms_parser.add_argument('--local-dir', type=str, default=None, help='Local directory to download files to')
    ms_parser.add_argument('--token', type=str, default=None, help='Access token for private models')

    # Cache management subcommand
    cache_parser = subparsers.add_parser("cache", help="Manage modely cache")
    cache_parser.add_argument('--cache-dir', type=str, default=None, help='Cache directory to use')
    cache_subparsers = cache_parser.add_subparsers(dest="cache_command", help="Cache commands")

    # modely cache info
    cache_info_parser = cache_subparsers.add_parser("info", help="Show cache information")

    # modely cache list
    cache_list_parser = cache_subparsers.add_parser("list", help="List cached repositories")
    cache_list_parser.add_argument("--detail", action="store_true", help="Show detailed file list")

    # modely cache clean
    cache_clean_parser = cache_subparsers.add_parser("clean", help="Clean cache")
    cache_clean_parser.add_argument("repo_id", nargs="?", default=None, help="Specific repo to clean (optional)")

    # modely cache config
    cache_config_parser = cache_subparsers.add_parser("config", help="Show or set cache directory")
    cache_config_parser.add_argument("--set", type=str, default=None, help="Set cache directory to this path")

    # Hugging Face subcommand
    hf_parser = subparsers.add_parser("hf", help="Download models from Hugging Face")
    hf_parser.add_argument('repo_id', type=str, help='Repository ID in format namespace/model_name')
    hf_parser.add_argument('--file', type=str, help='Specific file path to download from the repository')
    hf_parser.add_argument('--repo-type', choices=['model', 'dataset', 'space'], default='model', help='Type of repository (default: model)')
    hf_parser.add_argument('--revision', type=str, default='main', help='Revision of the model (default: main)')
    hf_parser.add_argument('--cache-dir', type=str, default=None, help='Cache directory for downloaded files')
    hf_parser.add_argument('--local-dir', type=str, default=None, help='Local directory to download files to')
    hf_parser.add_argument('--token', type=str, default=None, help='Access token for private repositories')
    hf_parser.add_argument('--force-download', action='store_true', help='Force re-download even if file exists')

    # GitHub subcommand
    github_parser = subparsers.add_parser("github", help="Download from GitHub")
    github_parser.add_argument('repo_id', type=str, help='Repository ID in format owner/repo')
    github_parser.add_argument('--file', type=str, help='Specific file to download')
    github_parser.add_argument('--revision', type=str, default='main', help='Branch, tag, or commit SHA (default: main)')
    github_parser.add_argument('--cache-dir', type=str, default=None, help='Cache directory for downloaded files')
    github_parser.add_argument('--local-dir', type=str, default=None, help='Local directory to download files to')
    github_parser.add_argument('--token', type=str, default=None, help='GitHub personal access token for private repositories')
    github_parser.add_argument('--with-lfs', action='store_true', help='Enable Git LFS support for large files')
    github_parser.add_argument('--force-download', action='store_true', help='Force re-download even if file exists')

    args = parser.parse_args()

    if args.command == "ms":
        try:
            if args.file:
                # Download a specific file
                if args.repo_type == 'model':
                    result = model_file_download(
                        model_id=args.repo_id,
                        file_path=args.file,
                        revision=args.revision,
                        cache_dir=args.cache_dir,
                        local_dir=args.local_dir,
                        token=args.token
                    )
                else:
                    result = dataset_file_download(
                        dataset_id=args.repo_id,
                        file_path=args.file,
                        revision=args.revision,
                        cache_dir=args.cache_dir,
                        local_dir=args.local_dir,
                        token=args.token
                    )
                print(f"Successfully downloaded file to: {result}")
            else:
                # Download entire repository
                result = modelscope_snapshot_download(
                    repo_id=args.repo_id,
                    repo_type=args.repo_type,
                    revision=args.revision,
                    cache_dir=args.cache_dir,
                    local_dir=args.local_dir,
                    token=args.token
                )
                if result is not None:
                    print(f"Repository download completed. Files are in: {result}")
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    elif args.command == "hf":
        try:
            if args.file:
                # Download a specific file
                result = hf_file_download(
                    repo_id=args.repo_id,
                    filename=args.file,
                    repo_type=args.repo_type,
                    revision=args.revision,
                    cache_dir=args.cache_dir,
                    local_dir=args.local_dir,
                    token=args.token,
                    force_download=args.force_download
                )
                print(f"Successfully downloaded file to: {result}")
            else:
                # Download entire repository
                result = hf_snapshot_download(
                    repo_id=args.repo_id,
                    repo_type=args.repo_type,
                    revision=args.revision,
                    cache_dir=args.cache_dir,
                    local_dir=args.local_dir,
                    token=args.token,
                    force_download=args.force_download
                )
                if result is not None:
                    print(f"Repository download completed. Files are in: {result}")
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    elif args.command == "github":
        try:
            if args.file:
                # Download a specific file
                result = github_file_download(
                    repo_id=args.repo_id,
                    filename=args.file,
                    revision=args.revision,
                    cache_dir=args.cache_dir,
                    local_dir=args.local_dir,
                    token=args.token,
                    force_download=args.force_download
                )
                print(f"Successfully downloaded file to: {result}")
            else:
                # Clone entire repository
                result = github_snapshot_download(
                    repo_id=args.repo_id,
                    revision=args.revision,
                    cache_dir=args.cache_dir,
                    local_dir=args.local_dir,
                    token=args.token,
                    with_lfs=args.with_lfs,
                    force_download=args.force_download
                )
                if result is not None:
                    print(f"Repository cloned to: {result}")
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    elif args.command == "cache":
        cache_main(args)
    else:
        parser.print_help()
        sys.exit(1)


def cache_main(args=None):
    """Handle cache subcommand."""
    if args is None:
        # If called directly
        parser = argparse.ArgumentParser(description="Manage modely cache")
        subparsers = parser.add_subparsers(dest="cache_command")

        info_parser = subparsers.add_parser("info")
        list_parser = subparsers.add_parser("list")
        list_parser.add_argument("--detail", action="store_true")
        clean_parser = subparsers.add_parser("clean")
        clean_parser.add_argument("repo_id", nargs="?", default=None)
        config_parser = subparsers.add_parser("config")
        config_parser.add_argument("--set", type=str, default=None)

        args = parser.parse_args()

    # Get cache_dir from args if provided
    cache_dir = getattr(args, "cache_dir", None)

    if args.cache_command == "info":
        info = cache.cache_info(cache_dir)
        print(f"Cache directory: {info['cache_dir']}")
        print(f"Total size: {info['total_size_str']}")
        print(f"Config file: {info['config_file']}")

    elif args.cache_command == "list":
        repos = cache.list_cache(cache_dir, detail=args.detail if hasattr(args, "detail") else False)
        if not repos:
            print("No cached repositories found.")
        else:
            for repo in repos:
                print(f"\n[{repo['source']}] {repo['repo_type']}: {repo['repo_id']} ({repo['revision']})")
                print(f"  Path: {repo['path']}")
                print(f"  Size: {repo['size_str']}")
                if args.detail and "files" in repo:
                    for f in repo["files"]:
                        print(f"    - {f['name']} ({f['size_str']})")

    elif args.cache_command == "clean":
        if args.repo_id:
            cleaned = cache.clean_cache(repo_id=args.repo_id, cache_dir=cache_dir)
            print(f"Cleaned {cache._format_size(cleaned)} for {args.repo_id}")
        else:
            cleaned = cache.clean_cache(cache_dir=cache_dir)
            print(f"Cleaned all cache: {cache._format_size(cleaned)}")

    elif args.cache_command == "config":
        if hasattr(args, "set") and args.set:
            cache.set_cache_dir(args.set)
            print(f"Cache directory set to: {args.set}")
        else:
            info = cache.cache_info(cache_dir)
            print(f"Current cache directory: {info['cache_dir']}")
            config = cache._load_config()
            if "cache_dir" in config:
                print(f"Configured in: {cache.CONFIG_FILE}")

    else:
        print("Usage: modely cache [info|list|clean|config]")
        sys.exit(1)


__all__ = [
    "main",
    "model_file_download",
    "dataset_file_download",
    "modelscope_snapshot_download",
    "hf_file_download",
    "hf_snapshot_download",
    "github_file_download",
    "github_snapshot_download",
    "HubApi",
    "cache",
    "cache_main"
]
