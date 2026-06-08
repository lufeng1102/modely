import os
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
from .watch import (
    configure_parser as configure_watch_parser,
    main as watch_main,
    run_watch,
    list_targets as watch_list_targets,
)
from .search import SearchResult, main as search_main
from .auth import delete_token, save_token, whoami
from .files import do_dry_run, format_file_size, list_repo_files, print_file_list
from .get import download_resource
from .info import get_repo_info, print_repo_info
from .manifest import create_download_manifest, create_lock, install_lock
from .sync import sync_resource
from .common import cache


def _format_file_size(size_bytes):
    """Format bytes into human-readable form."""
    return format_file_size(size_bytes)


def _print_file_list(files, source, repo_id):
    """Print a formatted table of repository files."""
    print_file_list(files, source, repo_id)


def _do_dry_run(source, repo_id, repo_type, revision, allow_patterns, ignore_patterns, files):
    """Simulate what would be downloaded and print a summary."""
    do_dry_run(source, repo_id, repo_type, revision, allow_patterns, ignore_patterns, files)


def _list_hf_files(repo_id, repo_type, revision, token, endpoint):
    """Fetch file listing from Hugging Face Hub."""
    from .hf import list_files
    try:
        files = list_files(repo_id, repo_type=repo_type, revision=revision, token=token, endpoint=endpoint)
        return [f.to_dict() | {"Path": f.path, "Size": f.size, "Type": f.type} for f in files]
    except Exception as e:
        print(f"Warning: Could not list files from HF: {e}", file=sys.stderr)
        return []


def _list_ms_files(repo_id, repo_type, revision, token):
    """Fetch file listing from ModelScope."""
    from .modelscope import HubApi
    api = HubApi(token=token)
    try:
        if repo_type == "model":
            files = api.get_model_files(repo_id, revision=revision)
        else:
            files = api.get_dataset_files(repo_id, revision=revision)
        return files
    except Exception as e:
        print(f"Warning: Could not list files from ModelScope: {e}", file=sys.stderr)
        return []


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
    ms_parser.add_argument('--include', nargs='+', default=None, help='Glob patterns to include (e.g., "*.json" "*.safetensors")')
    ms_parser.add_argument('--exclude', nargs='+', default=None, help='Glob patterns to exclude (e.g., "*.bin" "*.msgpack")')
    ms_parser.add_argument('--endpoint', type=str, default=None, help='ModelScope API endpoint')
    ms_parser.add_argument('--backend', choices=['auto', 'official', 'lightweight'], default='auto', help='ModelScope backend to use (default: auto)')
    ms_parser.add_argument('--list-files', action='store_true', help='List remote repository files without downloading')
    ms_parser.add_argument('--dry-run', action='store_true', help='Show what would be downloaded without downloading')

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
    hf_parser.add_argument('--include', nargs='+', default=None, help='Glob patterns to include (e.g., "*.json" "*.safetensors")')
    hf_parser.add_argument('--exclude', nargs='+', default=None, help='Glob patterns to exclude (e.g., "*.bin" "*.msgpack")')
    hf_parser.add_argument('--endpoint', type=str, default=None, help='HF API endpoint (e.g., https://hf-mirror.com)')
    hf_parser.add_argument('--list-files', action='store_true', help='List remote repository files without downloading')
    hf_parser.add_argument('--dry-run', action='store_true', help='Show what would be downloaded without downloading')

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
    github_parser.add_argument('--include', nargs='+', default=None, help='Sparse checkout/include patterns')
    github_parser.add_argument('--exclude', nargs='+', default=None, help='Glob patterns to remove after clone')
    github_parser.add_argument('--release', type=str, default=None, help='GitHub release tag for asset downloads/listing')
    github_parser.add_argument('--asset', type=str, default=None, help='GitHub release asset name to download')
    github_parser.add_argument('--submodules', action='store_true', help='Initialize git submodules after clone')

    # Unified info/files/download commands
    info_parser = subparsers.add_parser("info", help="Show repository metadata for a modely URI")
    info_parser.add_argument("resource", type=str, help="Resource URI, e.g. hf://models/gpt2")
    info_parser.add_argument('--revision', type=str, default=None)
    info_parser.add_argument('--token', type=str, default=None)
    info_parser.add_argument('--endpoint', type=str, default=None)
    info_parser.add_argument('--json', action='store_true')

    files_parser = subparsers.add_parser("files", help="List repository files for a modely URI")
    files_parser.add_argument("resource", type=str, help="Resource URI, e.g. hf://models/gpt2")
    files_parser.add_argument('--revision', type=str, default=None)
    files_parser.add_argument('--token', type=str, default=None)
    files_parser.add_argument('--endpoint', type=str, default=None)
    files_parser.add_argument('--release', type=str, default=None)
    files_parser.add_argument('--json', action='store_true')

    get_parser = subparsers.add_parser("get", help="Download by URI or auto-selected source")
    get_parser.add_argument("resource", type=str)
    get_parser.add_argument('--source', choices=['hf', 'ms', 'github', 'auto'], default='auto')
    get_parser.add_argument('--repo-type', choices=['model', 'dataset', 'space', 'tool'], default='model')
    get_parser.add_argument('--revision', type=str, default=None)
    get_parser.add_argument('--file', type=str, default=None)
    get_parser.add_argument('--cache-dir', type=str, default=None)
    get_parser.add_argument('--local-dir', type=str, default=None)
    get_parser.add_argument('--token', type=str, default=None)
    get_parser.add_argument('--include', nargs='+', default=None)
    get_parser.add_argument('--exclude', nargs='+', default=None)
    get_parser.add_argument('--prefer', type=str, default='ms,hf,github')
    get_parser.add_argument('--fallback', action='store_true')
    get_parser.add_argument('--force-download', action='store_true')
    get_parser.add_argument('--backend', choices=['auto', 'official', 'lightweight'], default='auto')
    get_parser.add_argument('--with-lfs', action='store_true')
    get_parser.add_argument('--manifest', type=str, default=None)
    get_parser.add_argument('--checksum', action='store_true')

    login_parser = subparsers.add_parser("login", help="Store a source token")
    login_parser.add_argument('source', choices=['hf', 'ms', 'github'])
    login_parser.add_argument('--token', required=True)
    logout_parser = subparsers.add_parser("logout", help="Remove a stored source token")
    logout_parser.add_argument('source', choices=['hf', 'ms', 'github'])
    whoami_parser = subparsers.add_parser("whoami", help="Show token status/identity")
    whoami_parser.add_argument('source', choices=['hf', 'ms', 'github'])
    whoami_parser.add_argument('--token', default=None)

    lock_parser = subparsers.add_parser("lock", help="Create a JSON lockfile for a resource")
    lock_parser.add_argument('resource', type=str)
    lock_parser.add_argument('--revision', type=str, default=None)
    lock_parser.add_argument('--include', nargs='+', default=None)
    lock_parser.add_argument('--exclude', nargs='+', default=None)
    lock_parser.add_argument('--output', '-o', default='modely.lock')
    lock_parser.add_argument('--token', default=None)

    install_parser = subparsers.add_parser("install", help="Install from a modely lockfile")
    install_parser.add_argument('-f', '--file', required=True)
    install_parser.add_argument('--local-dir', default=None)
    install_parser.add_argument('--cache-dir', default=None)
    install_parser.add_argument('--token', default=None)
    install_parser.add_argument('--force-download', action='store_true')

    sync_parser = subparsers.add_parser("sync", help="Download-only local sync of a resource")
    mirror_parser = subparsers.add_parser("mirror", help="Alias for sync")
    for p in (sync_parser, mirror_parser):
        p.add_argument('resource', type=str)
        p.add_argument('--local-dir', required=True)
        p.add_argument('--revision', type=str, default=None)
        p.add_argument('--include', nargs='+', default=None)
        p.add_argument('--exclude', nargs='+', default=None)
        p.add_argument('--token', default=None)
        p.add_argument('--cache-dir', default=None)
        p.add_argument('--manifest', default=None)
        p.add_argument('--checksum', action='store_true')
        p.add_argument('--force-download', action='store_true')
        p.add_argument('--source', choices=['hf', 'ms', 'github', 'auto'], default='auto')
        p.add_argument('--prefer', default='ms,hf,github')

    # Watch subcommand
    watch_parser = subparsers.add_parser("watch", help="Watch repositories and download updates")
    configure_watch_parser(watch_parser)

    # Search subcommand
    search_parser = subparsers.add_parser("search", help="Search for models and datasets")
    search_parser.add_argument("keyword", type=str, nargs="?", default=None, help="Search keyword for model/dataset name")
    search_parser.add_argument(
        "--source", "-s", choices=["hf", "ms", "github", "all"], default="all",
        help="Platform to search (default: all)",
    )
    search_parser.add_argument(
        "--repo-type", "-t", choices=["model", "dataset", "tool"], default="model",
        help="Type of repository (default: model)",
    )
    search_parser.add_argument(
        "--task", type=str, default=None,
        help="Filter by task type (e.g., text-classification)",
    )
    search_parser.add_argument(
        "--library", type=str, default=None,
        help="Filter by library (HF only, e.g., transformers, pytorch)",
    )
    search_parser.add_argument(
        "--license", type=str, default=None,
        help="Filter by license (HF only)",
    )
    search_parser.add_argument(
        "--sort", type=str, default="downloads",
        choices=["downloads", "lastModified", "likes", "created_at"],
        help="Sort field (default: downloads)",
    )
    search_parser.add_argument(
        "--direction", choices=["asc", "desc"], default="desc",
        help="Sort direction (default: desc)",
    )
    search_parser.add_argument(
        "--limit", "-n", type=int, default=20,
        help="Max results per source (default: 20)",
    )
    search_parser.add_argument(
        "--author", type=str, default=None,
        help="Filter by author/owner",
    )
    search_parser.add_argument(
        "--after", type=str, default=None,
        help="Only repos modified after this date (YYYY-MM-DD)",
    )
    search_parser.add_argument(
        "--before", type=str, default=None,
        help="Only repos modified before this date (YYYY-MM-DD)",
    )
    search_parser.add_argument(
        "--full", action="store_true",
        help="Return full model/dataset info (HF only)",
    )
    search_parser.add_argument(
        "--json", action="store_true",
        help="Output results as JSON",
    )

    args = parser.parse_args()

    if args.command == "ms":
        try:
            # Set ModelScope endpoint if provided
            if getattr(args, 'endpoint', None):
                os.environ['MODELSCOPE_ENDPOINT'] = args.endpoint

            # --list-files: show remote file listing
            if getattr(args, 'list_files', False):
                files = _list_ms_files(args.repo_id, args.repo_type, args.revision, args.token)
                _print_file_list(files, "ms", args.repo_id)
                return

            # --dry-run: preview what would be downloaded
            if getattr(args, 'dry_run', False):
                files = _list_ms_files(args.repo_id, args.repo_type, args.revision, args.token)
                _do_dry_run("ms", args.repo_id, args.repo_type, args.revision,
                            args.include, args.exclude, files)
                return

            if args.file:
                # Download a specific file
                if args.repo_type == 'model':
                    result = model_file_download(
                        model_id=args.repo_id,
                        file_path=args.file,
                        revision=args.revision,
                        cache_dir=args.cache_dir,
                        local_dir=args.local_dir,
                        token=args.token,
                        backend=args.backend
                    )
                else:
                    result = dataset_file_download(
                        dataset_id=args.repo_id,
                        file_path=args.file,
                        revision=args.revision,
                        cache_dir=args.cache_dir,
                        local_dir=args.local_dir,
                        token=args.token,
                        backend=args.backend
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
                    token=args.token,
                    allow_patterns=args.include,
                    ignore_patterns=args.exclude,
                    backend=args.backend,
                )
                if result is not None:
                    print(f"Repository download completed. Files are in: {result}")
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    elif args.command == "hf":
        try:
            # Set HF endpoint if provided
            if getattr(args, 'endpoint', None):
                os.environ['HF_ENDPOINT'] = args.endpoint

            # --list-files: show remote file listing
            if getattr(args, 'list_files', False):
                files = _list_hf_files(args.repo_id, args.repo_type, args.revision, args.token, args.endpoint)
                _print_file_list(files, "hf", args.repo_id)
                return

            # --dry-run: preview what would be downloaded
            if getattr(args, 'dry_run', False):
                files = _list_hf_files(args.repo_id, args.repo_type, args.revision, args.token, args.endpoint)
                _do_dry_run("hf", args.repo_id, args.repo_type, args.revision,
                            args.include, args.exclude, files)
                return

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
                    allow_patterns=args.include,
                    ignore_patterns=args.exclude,
                    force_download=args.force_download
                )
                if result is not None:
                    print(f"Repository download completed. Files are in: {result}")
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    elif args.command == "github":
        try:
            if getattr(args, 'asset', None):
                from .github import github_release_asset_download
                result = github_release_asset_download(
                    args.repo_id,
                    args.asset,
                    release=args.release,
                    cache_dir=args.cache_dir,
                    local_dir=args.local_dir,
                    token=args.token,
                    force_download=args.force_download,
                )
                print(f"Successfully downloaded release asset to: {result}")
            elif args.file:
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
                    force_download=args.force_download,
                    allow_patterns=args.include,
                    ignore_patterns=args.exclude,
                    submodules=args.submodules,
                )
                # github_clone() prints its own messages
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    elif args.command == "info":
        try:
            info = get_repo_info(args.resource, revision=args.revision, token=args.token, endpoint=args.endpoint)
            print_repo_info(info, as_json=args.json)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    elif args.command == "files":
        try:
            files = list_repo_files(args.resource, revision=args.revision, token=args.token, endpoint=args.endpoint, release=args.release)
            ref_source = args.resource.split("://", 1)[0] if "://" in args.resource else "hf"
            print_file_list(files, ref_source, args.resource, as_json=args.json)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    elif args.command == "get":
        try:
            result = download_resource(
                args.resource,
                source=args.source,
                repo_type=args.repo_type,
                revision=args.revision,
                file=args.file,
                cache_dir=args.cache_dir,
                local_dir=args.local_dir,
                token=args.token,
                include=args.include,
                exclude=args.exclude,
                prefer=args.prefer,
                fallback=args.fallback,
                force_download=args.force_download,
                backend=args.backend,
                with_lfs=args.with_lfs,
            )
            if args.manifest:
                create_download_manifest(args.resource if "://" in args.resource else f"hf://models/{args.resource}", result,
                                         include=args.include, exclude=args.exclude,
                                         checksum=args.checksum, output=args.manifest)
            print(f"Downloaded to: {result}")
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    elif args.command == "login":
        save_token(args.source, args.token)
        print(f"Token saved for {args.source}")
    elif args.command == "logout":
        removed = delete_token(args.source)
        print(f"Token removed for {args.source}" if removed else f"No stored token for {args.source}")
    elif args.command == "whoami":
        print(whoami(args.source, args.token))
    elif args.command == "lock":
        try:
            manifest = create_lock(args.resource, revision=args.revision, include=args.include,
                                   exclude=args.exclude, output=args.output, token=args.token)
            print(f"Wrote lockfile to: {args.output} ({len(manifest.files)} file(s))")
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    elif args.command == "install":
        try:
            result = install_lock(args.file, local_dir=args.local_dir, cache_dir=args.cache_dir,
                                  token=args.token, force_download=args.force_download)
            print(f"Installed to: {result}")
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    elif args.command in {"sync", "mirror"}:
        try:
            result = sync_resource(args.resource, local_dir=args.local_dir, revision=args.revision,
                                   include=args.include, exclude=args.exclude, token=args.token,
                                   cache_dir=args.cache_dir, manifest=args.manifest,
                                   checksum=args.checksum, force_download=args.force_download,
                                   source=args.source, prefer=args.prefer)
            print(f"Synced to: {result}")
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    elif args.command == "cache":
        cache_main(args)
    elif args.command == "watch":
        watch_main(args)
    elif args.command == "search":
        search_main(args)
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
    "cache_main",
    "watch_main",
    "run_watch",
    "watch_list_targets",
    "search",
    "SearchResult",
    "search_main",
]
