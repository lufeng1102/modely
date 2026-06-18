import os
import sys
import argparse
import json
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
from .backends import get_backend_capabilities, list_backends, print_backend_capabilities
from .analyze import analyze_resource, print_asset_analysis
from .card import get_card, print_card
from .compare import compare_resources, print_comparison
from .files import do_dry_run, format_file_size, list_repo_files, print_file_list
from .get import download_resource
from .info import get_repo_info, print_repo_info, resolve_repo_ref
from .manifest import create_download_manifest, create_lock, install_lock, print_lock_validation, validate_lock
from .mirror import print_mirror_verification, verify_mirror
from .doctor import doctor_resource, print_doctor_report
from .choose import choose_resource, print_choice
from .report import create_resource_report
from .benchmark import benchmark_sources, print_benchmark_results
from .batch import create_batch_download_plan, print_batch_download_result, run_batch_download
from .plan import create_download_plan, print_download_plan
from .profiles import PROFILES, resolve_download_profile
from .sources import list_source_profiles, print_probe_results, print_source_profiles, rank_sources
from .resolve import print_resolve_result, resolve_resource
from .policy import evaluate_catalog_policy, evaluate_scan_policy, load_policy, print_catalog_policy_result
from .scan import print_scan_result, scan_path, scan_resource
from .score import print_asset_score, score_path, score_resource
from .sync import sync_resource
from .catalog import (diff_catalogs, export_catalog, list_catalog_snapshots, print_catalog_diff,
                      print_catalog_report, read_catalog_report, scan_catalog, snapshot_catalog, write_catalog_report)
from .uri import concrete_repo_type, parse_modely_uri
from .common import cache
from .cache_web import serve_cache_browser


# Stable public Python API aliases. Avoid aliases that shadow submodules such as
# modely.scan or modely.compare so monkeypatching and module imports stay compatible.
download = download_resource
catalog_scan = scan_catalog

__all__ = [
    "SearchResult", "download", "download_resource", "resolve_resource",
    "compare_resources", "verify_mirror", "scan_resource", "scan_path",
    "score_resource", "score_path", "create_lock", "install_lock", "validate_lock",
    "catalog_scan", "scan_catalog", "choose_resource", "list_source_profiles",
    "rank_sources", "get_repo_info", "list_repo_files",
]


_COMMAND_GROUPS = [
    (
        "Download and sync",
        [
            ("hf", "Download models or datasets from Hugging Face"),
            ("ms", "Download models or datasets from ModelScope"),
            ("github", "Download repositories, files, or release assets from GitHub"),
            ("get", "Download by modely URI or auto-selected source"),
            ("batch-download", "Search, preview, and batch download matching resources"),
            ("sync", "Download-only local sync of a resource"),
            ("mirror", "Alias for sync"),
        ],
    ),
    (
        "Query and evaluate",
        [
            ("info", "Show repository metadata for a modely URI"),
            ("files", "List and summarize repository files for a modely URI"),
            ("plan", "Dry-run a download plan without downloading"),
            ("card", "Fetch and parse a model, dataset, or repository card"),
            ("analyze", "Analyze metadata, files, cards, and weight formats"),
            ("score", "Score resource health from metadata and file lists"),
            ("scan", "Scan metadata, safety, and reproducibility risks"),
            ("compare", "Deep-compare two explicit modely resources"),
            ("resolve", "Find likely equivalent resources across sources"),
        ],
    ),
    (
        "Search and choose sources",
        [
            ("search", "Search for models, datasets, and AI/ML repositories"),
            ("doctor", "Diagnose and recommend a modely resource"),
            ("choose", "Choose the best source for a resource query"),
            ("sources", "List or probe source endpoints"),
            ("capabilities", "Show source/backend capability support"),
        ],
    ),
    (
        "Reproducibility and inventory",
        [
            ("lock", "Create a JSON lockfile for a resource"),
            ("install", "Install files from a modely lockfile"),
            ("validate-lock", "Validate a lockfile against local files"),
            ("catalog", "Inventory local or cached modely assets"),
            ("verify-mirror", "Verify two resources appear mirror-equivalent"),
            ("report", "Generate a resource report"),
            ("benchmark", "Check source endpoint availability and latency"),
        ],
    ),
    (
        "Account, monitoring, and cache",
        [
            ("login", "Store a source token"),
            ("logout", "Remove a stored source token"),
            ("whoami", "Show token status or identity"),
            ("watch", "Watch repositories and download updates"),
            ("cache", "Manage the modely cache"),
        ],
    ),
]


_COMMAND_HELP = {command: help_text for _, commands in _COMMAND_GROUPS for command, help_text in commands}
_SOURCE_CHOICES = ('hf', 'ms', 'github', 'kaggle', 'auto')
_REPO_TYPE_CHOICES = ('auto', 'model', 'dataset', 'space', 'tool', 'competition')
_GET_REPO_TYPE_CHOICES = ('auto', 'model', 'dataset', 'space', 'tool')


def _add_source_repo_type_args(command_parser, *, repo_type_choices=_REPO_TYPE_CHOICES):
    command_parser.add_argument('--source', choices=_SOURCE_CHOICES, default='auto')
    command_parser.add_argument('--repo-type', choices=repo_type_choices, default='auto')


def _format_command_groups() -> str:
    lines = ["Command categories:"]
    for title, commands in _COMMAND_GROUPS:
        lines.append(f"  {title}:")
        width = max(len(command) for command, _ in commands)
        for command, help_text in commands:
            lines.append(f"    {command:<{width}}  {help_text}")
    return "\n".join(lines)


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
    parser = argparse.ArgumentParser(
        prog="modely",
        description="Modely - unified model and dataset download, discovery, and governance CLI",
        epilog=_format_command_groups(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND", help=argparse.SUPPRESS)

    # ModelScope subcommand (renamed to "ms")
    ms_parser = subparsers.add_parser("ms", help=_COMMAND_HELP["ms"])
    ms_parser.add_argument('repo_id', type=str, help='Repository ID in format owner/name')
    ms_parser.add_argument('--file', type=str, help='Specific file path to download from the repository')
    ms_parser.add_argument('--repo-type', choices=['auto', 'model', 'dataset'], default='auto', help='Type of repository (default: auto)')
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
    cache_parser = subparsers.add_parser("cache", help=_COMMAND_HELP["cache"])
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

    cache_dedupe_parser = cache_subparsers.add_parser("dedupe", help="Report duplicate files in cache")
    cache_dedupe_parser.add_argument("--dry-run", action="store_true", help="Report only; do not modify files")
    cache_dedupe_parser.add_argument("--json", action="store_true")
    cache_serve_parser = cache_subparsers.add_parser("serve", help="Serve a read-only local cache browser")
    cache_serve_parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    cache_serve_parser.add_argument("--port", type=int, default=8765, help="Port to bind (default: 8765)")
    cache_serve_parser.add_argument("--open", action="store_true", help="Open the browser after starting")

    # Hugging Face subcommand
    hf_parser = subparsers.add_parser("hf", help=_COMMAND_HELP["hf"])
    hf_parser.add_argument('repo_id', type=str, help='Repository ID in format namespace/model_name')
    hf_parser.add_argument('--file', type=str, help='Specific file path to download from the repository')
    hf_parser.add_argument('--repo-type', choices=['auto', 'model', 'dataset', 'space'], default='auto', help='Type of repository (default: auto)')
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
    github_parser = subparsers.add_parser("github", help=_COMMAND_HELP["github"])
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
    info_parser = subparsers.add_parser("info", help=_COMMAND_HELP["info"])
    info_parser.add_argument("resource", type=str, help="Resource URI, e.g. hf://models/gpt2")
    _add_source_repo_type_args(info_parser)
    info_parser.add_argument('--revision', type=str, default=None)
    info_parser.add_argument('--token', type=str, default=None)
    info_parser.add_argument('--endpoint', type=str, default=None)
    info_parser.add_argument('--json', action='store_true')

    files_parser = subparsers.add_parser("files", help=_COMMAND_HELP["files"])
    files_parser.add_argument("resource", type=str, help="Resource URI, e.g. hf://models/gpt2")
    _add_source_repo_type_args(files_parser)
    files_parser.add_argument('--revision', type=str, default=None)
    files_parser.add_argument('--token', type=str, default=None)
    files_parser.add_argument('--endpoint', type=str, default=None)
    files_parser.add_argument('--release', type=str, default=None)
    files_parser.add_argument('--include', nargs='+', default=None)
    files_parser.add_argument('--exclude', nargs='+', default=None)
    files_parser.add_argument('--profile', choices=list(PROFILES), default=None)
    files_parser.add_argument('--summary', action='store_true')
    files_parser.add_argument('--json', action='store_true')

    plan_parser = subparsers.add_parser("plan", help=_COMMAND_HELP["plan"])
    plan_parser.add_argument("resource", type=str)
    _add_source_repo_type_args(plan_parser)
    plan_parser.add_argument('--revision', type=str, default=None)
    plan_parser.add_argument('--include', nargs='+', default=None)
    plan_parser.add_argument('--exclude', nargs='+', default=None)
    plan_parser.add_argument('--profile', choices=list(PROFILES), default=None)
    plan_parser.add_argument('--cache-dir', default=None)
    plan_parser.add_argument('--local-dir', default=None)
    plan_parser.add_argument('--token', default=None)
    plan_parser.add_argument('--endpoint', default=None)
    plan_parser.add_argument('--release', default=None)
    plan_parser.add_argument('--json', action='store_true')

    card_parser = subparsers.add_parser("card", help=_COMMAND_HELP["card"])
    card_parser.add_argument("resource", type=str)
    _add_source_repo_type_args(card_parser)
    card_parser.add_argument('--revision', type=str, default=None)
    card_parser.add_argument('--token', default=None)
    card_parser.add_argument('--endpoint', default=None)
    card_parser.add_argument('--json', action='store_true')

    analyze_parser = subparsers.add_parser("analyze", help=_COMMAND_HELP["analyze"])
    analyze_parser.add_argument("resource", type=str)
    _add_source_repo_type_args(analyze_parser)
    analyze_parser.add_argument('--revision', type=str, default=None)
    analyze_parser.add_argument('--token', default=None)
    analyze_parser.add_argument('--endpoint', default=None)
    analyze_parser.add_argument('--include', nargs='+', default=None)
    analyze_parser.add_argument('--exclude', nargs='+', default=None)
    analyze_parser.add_argument('--profile', choices=list(PROFILES), default=None)
    analyze_parser.add_argument('--top-files', type=int, default=5)
    analyze_parser.add_argument('--deep', action='store_true', help='Add metadata-derived format, quantization, profile, and risk analysis')
    analyze_parser.add_argument('--json', action='store_true')

    score_parser = subparsers.add_parser("score", help=_COMMAND_HELP["score"])
    score_parser.add_argument("resource")
    _add_source_repo_type_args(score_parser)
    score_parser.add_argument('--revision', type=str, default=None)
    score_parser.add_argument('--token', default=None)
    score_parser.add_argument('--endpoint', default=None)
    score_parser.add_argument('--include', nargs='+', default=None)
    score_parser.add_argument('--exclude', nargs='+', default=None)
    score_parser.add_argument('--profile', choices=list(PROFILES), default=None)
    score_parser.add_argument('--no-deep', action='store_true', help='Disable deep metadata-derived scoring')
    score_parser.add_argument('--local', action='store_true', help='Score a local directory without network access')
    score_parser.add_argument('--json', action='store_true')

    scan_parser = subparsers.add_parser("scan", help=_COMMAND_HELP["scan"])
    scan_parser.add_argument("resource")
    _add_source_repo_type_args(scan_parser)
    scan_parser.add_argument('--revision', type=str, default=None)
    scan_parser.add_argument('--token', default=None)
    scan_parser.add_argument('--endpoint', default=None)
    scan_parser.add_argument('--include', nargs='+', default=None)
    scan_parser.add_argument('--exclude', nargs='+', default=None)
    scan_parser.add_argument('--profile', choices=list(PROFILES), default=None)
    scan_parser.add_argument('--no-deep', action='store_true', help='Disable deep metadata-derived scanning')
    scan_parser.add_argument('--local', action='store_true', help='Scan a local directory without network access')
    scan_parser.add_argument('--inspect-files', action='store_true', help='Inspect small remote text/code files for suspicious patterns')
    scan_parser.add_argument('--fail-on', choices=['low', 'medium', 'high'], default=None, help='Exit nonzero if findings meet this severity')
    scan_parser.add_argument('--policy', default=None, help='JSON policy file for scan evaluation')
    scan_parser.add_argument('--json', action='store_true')

    compare_parser = subparsers.add_parser("compare", help=_COMMAND_HELP["compare"])
    compare_parser.add_argument("left", type=str)
    compare_parser.add_argument("right", type=str)
    compare_parser.add_argument('--revision-left', default=None)
    compare_parser.add_argument('--revision-right', default=None)
    compare_parser.add_argument('--token', default=None)
    compare_parser.add_argument('--files', action='store_true', help='Include added/removed/common file details')
    compare_parser.add_argument('--card', action='store_true', help='Include normalized card metadata differences')
    compare_parser.add_argument('--formats', action='store_true', help='Include weight format differences')
    compare_parser.add_argument('--deep', action='store_true', help='Run deep analysis before comparing')
    compare_parser.add_argument('--json', action='store_true')

    get_parser = subparsers.add_parser("get", help=_COMMAND_HELP["get"])
    get_parser.add_argument("resource", nargs="+", help="Resource URI/repo, or SOURCE RESOURCE for compatibility")
    _add_source_repo_type_args(get_parser, repo_type_choices=_GET_REPO_TYPE_CHOICES)
    get_parser.add_argument('--revision', type=str, default=None)
    get_parser.add_argument('--file', type=str, default=None)
    get_parser.add_argument('--cache-dir', type=str, default=None)
    get_parser.add_argument('--local-dir', type=str, default=None)
    get_parser.add_argument('--token', type=str, default=None)
    get_parser.add_argument('--include', nargs='+', default=None)
    get_parser.add_argument('--exclude', nargs='+', default=None)
    get_parser.add_argument('--prefer', type=str, default='default')
    get_parser.add_argument('--fallback', action='store_true')
    get_parser.add_argument('--force-download', action='store_true')
    get_parser.add_argument('--backend', choices=['auto', 'official', 'lightweight'], default='auto')
    get_parser.add_argument('--with-lfs', action='store_true')
    get_parser.add_argument('--manifest', type=str, default=None)
    get_parser.add_argument('--checksum', action='store_true')
    get_parser.add_argument('--profile', choices=list(PROFILES), default=None)
    get_parser.add_argument('--endpoint', type=str, default=None)
    get_parser.add_argument('--max-workers', type=int, default=None)
    get_parser.add_argument('--timeout', type=float, default=None)
    get_parser.add_argument('--retries', type=int, default=None)
    get_parser.add_argument('--no-resume', action='store_true', help='Disable backend resume behavior where supported')

    sources_parser = subparsers.add_parser("sources", help=_COMMAND_HELP["sources"])
    sources_subparsers = sources_parser.add_subparsers(dest="sources_command")
    sources_list_parser = sources_subparsers.add_parser("list", help="List source profiles")
    sources_list_parser.add_argument('--source', choices=['hf', 'ms', 'github', 'kaggle', 'all'], default='all')
    sources_list_parser.add_argument('--json', action='store_true')
    sources_probe_parser = sources_subparsers.add_parser("probe", help="Probe source endpoints")
    sources_probe_parser.add_argument('resource', nargs='?', default=None)
    sources_probe_parser.add_argument('--source', choices=['hf', 'ms', 'github', 'kaggle', 'all'], default='all')
    sources_probe_parser.add_argument('--timeout', type=float, default=5)
    sources_probe_parser.add_argument('--json', action='store_true')

    capabilities_parser = subparsers.add_parser("capabilities", help=_COMMAND_HELP["capabilities"])
    capabilities_parser.add_argument('--source', choices=['hf', 'ms', 'github', 'kaggle', 'http', 'all'], default='all')
    capabilities_parser.add_argument('--backend', default=None, help='Specific backend or source alias to inspect')
    capabilities_parser.add_argument('--json', action='store_true')

    login_parser = subparsers.add_parser("login", help=_COMMAND_HELP["login"])
    login_parser.add_argument('source', choices=['hf', 'ms', 'github', 'kaggle'])
    login_parser.add_argument('--username', help='Kaggle username; stored guidance only, prefer KAGGLE_USERNAME for runtime')
    login_group = login_parser.add_mutually_exclusive_group(required=True)
    login_group.add_argument('--token')
    login_group.add_argument('--stdin', action='store_true', help='Read token from stdin')
    logout_parser = subparsers.add_parser("logout", help=_COMMAND_HELP["logout"])
    logout_parser.add_argument('source', choices=['hf', 'ms', 'github', 'kaggle'])
    whoami_parser = subparsers.add_parser("whoami", help=_COMMAND_HELP["whoami"])
    whoami_parser.add_argument('source', choices=['hf', 'ms', 'github', 'kaggle'])
    whoami_parser.add_argument('--token', default=None)

    lock_parser = subparsers.add_parser("lock", help=_COMMAND_HELP["lock"])
    lock_parser.add_argument('resource', type=str)
    lock_parser.add_argument('--revision', type=str, default=None)
    lock_parser.add_argument('--include', nargs='+', default=None)
    lock_parser.add_argument('--exclude', nargs='+', default=None)
    lock_parser.add_argument('--profile', choices=list(PROFILES), default=None)
    lock_parser.add_argument('--endpoint', default=None)
    lock_parser.add_argument('--output', '-o', default='modely.lock')
    lock_parser.add_argument('--token', default=None)
    lock_parser.add_argument('--alternatives', default=None, help='Comma-separated fallback source list to record in the lockfile')
    lock_parser.add_argument('--strict', action='store_true', help='Fail if lock metadata is not fully reproducible')
    lock_parser.add_argument('--require-checksums', action='store_true', help='Require SHA256 metadata for all selected files')
    lock_parser.add_argument('--json', action='store_true')

    install_parser = subparsers.add_parser("install", help=_COMMAND_HELP["install"])
    install_parser.add_argument('-f', '--file', required=True)
    install_parser.add_argument('--local-dir', default=None)
    install_parser.add_argument('--cache-dir', default=None)
    install_parser.add_argument('--token', default=None)
    install_parser.add_argument('--force-download', action='store_true')
    install_parser.add_argument('--fallback', action='store_true', help='Try alternate sources from lock metadata or --prefer')
    install_parser.add_argument('--prefer', default=None, help='Comma-separated source order for fallback installs')

    validate_lock_parser = subparsers.add_parser("validate-lock", help=_COMMAND_HELP["validate-lock"])
    validate_lock_parser.add_argument('-f', '--file', required=True)
    validate_lock_parser.add_argument('--local-dir', default=None)
    validate_lock_parser.add_argument('--checksum', action='store_true')
    validate_lock_parser.add_argument('--strict', action='store_true', help='Require sizes and checksums to match')
    validate_lock_parser.add_argument('--require-checksums', action='store_true', help='Fail when lock entries lack checksums')
    validate_lock_parser.add_argument('--json', action='store_true')

    catalog_parser = subparsers.add_parser("catalog", help=_COMMAND_HELP["catalog"])
    catalog_subparsers = catalog_parser.add_subparsers(dest="catalog_command")
    catalog_scan_parser = catalog_subparsers.add_parser("scan", help="Scan a local directory or modely cache into a catalog report")
    catalog_scan_parser.add_argument("root", nargs="?", default=None, help="Local root directory to scan")
    catalog_scan_parser.add_argument('--cache', action='store_true', help='Catalog the modely cache instead of a local root')
    catalog_scan_parser.add_argument('--cache-dir', default=None)
    catalog_scan_parser.add_argument('--score', action='store_true', help='Attach score summaries using local analysis by default')
    catalog_scan_parser.add_argument('--scan', action='store_true', help='Attach scan summaries')
    catalog_scan_parser.add_argument('--remote', action='store_true', help='Allow network metadata calls for score/scan enrichment')
    catalog_scan_parser.add_argument('--fail-on', choices=['low', 'medium', 'high'], default=None, help='Policy threshold for attached scan summaries')
    catalog_scan_parser.add_argument('--policy', default=None, help='JSON policy file for scan evaluation')
    catalog_scan_parser.add_argument('--snapshot', action='store_true', help='Save the catalog report as a history snapshot')
    catalog_scan_parser.add_argument('--history-dir', default='.modely/catalog', help='Catalog snapshot directory')
    catalog_scan_parser.add_argument('--token', default=None)
    catalog_scan_parser.add_argument('--endpoint', default=None)
    catalog_scan_parser.add_argument('--output', '-o', default=None, help='Write JSON report to a file')
    catalog_scan_parser.add_argument('--json', action='store_true')
    catalog_diff_parser = catalog_subparsers.add_parser("diff", help="Compare two catalog reports")
    catalog_diff_parser.add_argument("left")
    catalog_diff_parser.add_argument("right")
    catalog_diff_parser.add_argument('--json', action='store_true')
    catalog_export_parser = catalog_subparsers.add_parser("export", help="Export a catalog report")
    catalog_export_parser.add_argument("report")
    catalog_export_parser.add_argument('--format', choices=['csv'], default='csv')
    catalog_export_parser.add_argument('--output', '-o', default=None)
    catalog_history_parser = catalog_subparsers.add_parser("history", help="List catalog snapshots")
    catalog_history_parser.add_argument('--dir', default='.modely/catalog')
    catalog_history_parser.add_argument('--json', action='store_true')
    catalog_gate_parser = catalog_subparsers.add_parser("gate", help="Evaluate a catalog report against scan policy")
    catalog_gate_parser.add_argument("report")
    catalog_gate_parser.add_argument('--fail-on', choices=['low', 'medium', 'high'], default=None)
    catalog_gate_parser.add_argument('--policy', default=None)
    catalog_gate_parser.add_argument('--json', action='store_true')

    doctor_parser = subparsers.add_parser("doctor", help=_COMMAND_HELP["doctor"])
    doctor_parser.add_argument("query")
    doctor_parser.add_argument('--source', choices=['hf', 'ms', 'github', 'kaggle', 'all'], default='all')
    doctor_parser.add_argument('--repo-type', choices=['auto', 'model', 'dataset', 'tool'], default='auto')
    doctor_parser.add_argument('--strategy', choices=['balanced', 'safest', 'fastest', 'freshest'], default='balanced')
    doctor_parser.add_argument('--probe', action='store_true')
    doctor_parser.add_argument('--limit', type=int, default=5)
    doctor_parser.add_argument('--threshold', type=float, default=0.35)
    doctor_parser.add_argument('--token', default=None)
    doctor_parser.add_argument('--endpoint', default=None)
    doctor_parser.add_argument('--json', action='store_true')

    choose_parser = subparsers.add_parser("choose", help=_COMMAND_HELP["choose"])
    choose_parser.add_argument("query")
    choose_parser.add_argument('--source', choices=['hf', 'ms', 'github', 'kaggle', 'all'], default='all')
    choose_parser.add_argument('--repo-type', choices=['auto', 'model', 'dataset', 'tool'], default='auto')
    choose_parser.add_argument('--strategy', choices=['balanced', 'safest', 'fastest', 'freshest'], default='balanced')
    choose_parser.add_argument('--limit', type=int, default=5)
    choose_parser.add_argument('--threshold', type=float, default=0.35)
    choose_parser.add_argument('--token', default=None)
    choose_parser.add_argument('--endpoint', default=None)
    choose_parser.add_argument('--json', action='store_true')

    mirror_verify_parser = subparsers.add_parser("verify-mirror", help=_COMMAND_HELP["verify-mirror"])
    mirror_verify_parser.add_argument("left")
    mirror_verify_parser.add_argument("right")
    mirror_verify_parser.add_argument('--token', default=None)
    mirror_verify_parser.add_argument('--no-deep', action='store_true')
    mirror_verify_parser.add_argument('--json', action='store_true')

    report_parser = subparsers.add_parser("report", help=_COMMAND_HELP["report"])
    report_parser.add_argument("resource")
    report_parser.add_argument('--format', choices=['markdown', 'html', 'json'], default='markdown')
    report_parser.add_argument('--source', choices=['hf', 'ms', 'github', 'kaggle', 'all'], default='all')
    report_parser.add_argument('--repo-type', choices=['auto', 'model', 'dataset', 'tool'], default='auto')
    report_parser.add_argument('--output', '-o', default=None)

    benchmark_parser = subparsers.add_parser("benchmark", help=_COMMAND_HELP["benchmark"])
    benchmark_parser.add_argument("resource", nargs="?", default=None)
    benchmark_parser.add_argument('--source', '--sources', dest='sources', default='all')
    benchmark_parser.add_argument('--url', default=None)
    benchmark_parser.add_argument('--timeout', type=float, default=5)
    benchmark_parser.add_argument('--json', action='store_true')

    batch_parser = subparsers.add_parser("batch-download", help=_COMMAND_HELP["batch-download"])
    batch_parser.add_argument("keyword", nargs="?", default=None)
    batch_parser.add_argument('--tag', action='append', default=None, help='Filter by tag; repeat for AND matching')
    batch_parser.add_argument('--source', choices=['hf', 'ms', 'github', 'kaggle', 'all'], default='all')
    batch_parser.add_argument('--repo-type', choices=['auto', 'model', 'dataset'], default='auto')
    batch_parser.add_argument('--limit', type=int, default=20, help='Maximum matching resources to download')
    batch_parser.add_argument('--search-limit', type=int, default=None, help='Maximum results to fetch per source before tag filtering')
    batch_parser.add_argument('--task', default=None)
    batch_parser.add_argument('--library', default=None)
    batch_parser.add_argument('--license', default=None)
    batch_parser.add_argument('--sort', choices=['downloads', 'lastModified', 'likes', 'created_at'], default='downloads')
    batch_parser.add_argument('--direction', choices=['asc', 'desc'], default='desc')
    batch_parser.add_argument('--author', default=None)
    batch_parser.add_argument('--after', default=None)
    batch_parser.add_argument('--before', default=None)
    batch_parser.add_argument('--full', action='store_true')
    batch_parser.add_argument('--local-dir', default=None)
    batch_parser.add_argument('--cache-dir', default=None)
    batch_parser.add_argument('--token', default=None)
    batch_parser.add_argument('--include', nargs='+', default=None)
    batch_parser.add_argument('--exclude', nargs='+', default=None)
    batch_parser.add_argument('--profile', choices=list(PROFILES), default=None)
    batch_parser.add_argument('--prefer', default='default')
    batch_parser.add_argument('--fallback', action='store_true')
    batch_parser.add_argument('--force-download', action='store_true')
    batch_parser.add_argument('--backend', choices=['auto', 'official', 'lightweight'], default='auto')
    batch_parser.add_argument('--with-lfs', action='store_true')
    batch_parser.add_argument('--endpoint', default=None)
    batch_parser.add_argument('--max-workers', type=int, default=None)
    batch_parser.add_argument('--timeout', type=float, default=None)
    batch_parser.add_argument('--retries', type=int, default=None)
    batch_parser.add_argument('--checksum', action='store_true')
    batch_parser.add_argument('--no-resume', action='store_true')
    batch_parser.add_argument('--fail-fast', action='store_true')
    batch_parser.add_argument('--yes', action='store_true', help='Execute downloads instead of dry-run')
    batch_parser.add_argument('--json', action='store_true')

    sync_parser = subparsers.add_parser("sync", help=_COMMAND_HELP["sync"])
    mirror_parser = subparsers.add_parser("mirror", help=_COMMAND_HELP["mirror"])
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
        p.add_argument('--source', choices=['hf', 'ms', 'github', 'kaggle', 'auto'], default='auto')
        p.add_argument('--prefer', default='default')
        p.add_argument('--profile', choices=list(PROFILES), default=None)
        p.add_argument('--report', default=None, help='Write a JSON sync/mirror report')
        p.add_argument('--analyze', action='store_true', help='Include remote asset analysis in the report')
        p.add_argument('--compare-to', default=None, help='Compare the synced resource to another modely URI in the report')
        p.add_argument('--deep', action='store_true', help='Use deep analysis for report analysis/comparison')

    # Watch subcommand
    watch_parser = subparsers.add_parser("watch", help=_COMMAND_HELP["watch"])
    configure_watch_parser(watch_parser)

    # Resolve subcommand
    resolve_parser = subparsers.add_parser("resolve", help=_COMMAND_HELP["resolve"])
    resolve_parser.add_argument("query", type=str, help="Model/dataset name or modely URI to resolve")
    resolve_parser.add_argument(
        "--source", "-s", choices=["hf", "ms", "github", "kaggle", "all"], default="all",
        help="Platform to search (default: all)",
    )
    resolve_parser.add_argument(
        "--repo-type", "-t", choices=["auto", "model", "dataset", "tool"], default="auto",
        help="Type of repository (default: auto)",
    )
    resolve_parser.add_argument("--task", default=None, help="Filter by task type")
    resolve_parser.add_argument("--library", default=None, help="Filter by library where supported")
    resolve_parser.add_argument("--license", default=None, help="Filter by license where supported")
    resolve_parser.add_argument("--limit", "-n", type=int, default=10, help="Max results per source")
    resolve_parser.add_argument("--threshold", type=float, default=0.35, help="Minimum confidence to include")
    resolve_parser.add_argument("--full", action="store_true", help="Request richer backend metadata where supported")
    resolve_parser.add_argument("--json", action="store_true", help="Output result as JSON")

    # Search subcommand
    search_parser = subparsers.add_parser("search", help=_COMMAND_HELP["search"])
    search_parser.add_argument("keyword", type=str, nargs="?", default=None, help="Search keyword for model/dataset name")
    search_parser.add_argument(
        "--source", "-s", choices=["hf", "ms", "github", "kaggle", "all"], default="all",
        help="Platform to search (default: all)",
    )
    search_parser.add_argument(
        "--repo-type", "-t", choices=["auto", "model", "dataset", "tool"], default="auto",
        help="Type of repository (default: auto)",
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
    search_parser.add_argument(
        "--dedupe", action="store_true",
        help="Group search results by normalized repository name",
    )
    search_parser.add_argument(
        "--compare", action="store_true",
        help="Show grouped search-result comparison rows",
    )

    args = parser.parse_args()

    if args.command == "ms":
        try:
            repo_type = concrete_repo_type(args.repo_type, "ms")
            # Set ModelScope endpoint if provided
            if getattr(args, 'endpoint', None):
                os.environ['MODELSCOPE_ENDPOINT'] = args.endpoint

            # --list-files: show remote file listing
            if getattr(args, 'list_files', False):
                files = _list_ms_files(args.repo_id, repo_type, args.revision, args.token)
                _print_file_list(files, "ms", args.repo_id)
                return

            # --dry-run: preview what would be downloaded
            if getattr(args, 'dry_run', False):
                files = _list_ms_files(args.repo_id, repo_type, args.revision, args.token)
                _do_dry_run("ms", args.repo_id, repo_type, args.revision,
                            args.include, args.exclude, files)
                return

            if args.file:
                # Download a specific file
                if repo_type == 'model':
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
                    repo_type=repo_type,
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
            repo_type = concrete_repo_type(args.repo_type, "hf")
            # Set HF endpoint if provided
            if getattr(args, 'endpoint', None):
                os.environ['HF_ENDPOINT'] = args.endpoint

            # --list-files: show remote file listing
            if getattr(args, 'list_files', False):
                files = _list_hf_files(args.repo_id, repo_type, args.revision, args.token, args.endpoint)
                _print_file_list(files, "hf", args.repo_id)
                return

            # --dry-run: preview what would be downloaded
            if getattr(args, 'dry_run', False):
                files = _list_hf_files(args.repo_id, repo_type, args.revision, args.token, args.endpoint)
                _do_dry_run("hf", args.repo_id, repo_type, args.revision,
                            args.include, args.exclude, files)
                return

            if args.file:
                # Download a specific file
                result = hf_file_download(
                    repo_id=args.repo_id,
                    filename=args.file,
                    repo_type=repo_type,
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
                    repo_type=repo_type,
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
            info = get_repo_info(args.resource, revision=args.revision, token=args.token, endpoint=args.endpoint,
                                 source=args.source, repo_type=args.repo_type)
            print_repo_info(info, as_json=args.json)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    elif args.command == "files":
        try:
            include, exclude = resolve_download_profile(args.profile, args.include, args.exclude)
            if args.release:
                ref = parse_modely_uri(args.resource, source=args.source, repo_type=args.repo_type)
            else:
                ref = resolve_repo_ref(args.resource, revision=args.revision, token=args.token, endpoint=args.endpoint,
                                       source=args.source, repo_type=args.repo_type)
            files = list_repo_files(ref, revision=args.revision, token=args.token, endpoint=args.endpoint,
                                    release=args.release)
            from .files import filter_files
            files = filter_files(files, include, exclude)
            print_file_list(files, ref.source, ref.repo_id, as_json=args.json, summary=args.summary)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    elif args.command == "plan":
        try:
            plan = create_download_plan(args.resource, source=args.source, repo_type=args.repo_type,
                                        revision=args.revision, include=args.include, exclude=args.exclude,
                                        profile=args.profile, token=args.token, endpoint=args.endpoint,
                                        cache_dir=args.cache_dir, local_dir=args.local_dir, release=args.release)
            print_download_plan(plan, as_json=args.json)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    elif args.command == "card":
        try:
            card = get_card(args.resource, revision=args.revision, token=args.token, endpoint=args.endpoint,
                            source=args.source, repo_type=args.repo_type)
            print_card(card, as_json=args.json)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    elif args.command == "analyze":
        try:
            analysis = analyze_resource(args.resource, revision=args.revision, token=args.token,
                                        endpoint=args.endpoint, include=args.include, exclude=args.exclude,
                                        profile=args.profile, top_files=args.top_files, deep=args.deep,
                                        source=args.source, repo_type=args.repo_type)
            print_asset_analysis(analysis, as_json=args.json)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    elif args.command == "score":
        try:
            if args.local or (os.path.exists(args.resource) and "://" not in args.resource):
                result = score_path(args.resource, deep=not args.no_deep)
            else:
                result = score_resource(args.resource, revision=args.revision, token=args.token,
                                        endpoint=args.endpoint, include=args.include, exclude=args.exclude,
                                        profile=args.profile, deep=not args.no_deep,
                                        source=args.source, repo_type=args.repo_type)
            print_asset_score(result, as_json=args.json)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    elif args.command == "scan":
        try:
            if args.local or (os.path.exists(args.resource) and "://" not in args.resource):
                result = scan_path(args.resource, deep=not args.no_deep)
            else:
                result = scan_resource(args.resource, revision=args.revision, token=args.token,
                                       endpoint=args.endpoint, include=args.include, exclude=args.exclude,
                                       profile=args.profile, deep=not args.no_deep, inspect_files=args.inspect_files,
                                       source=args.source, repo_type=args.repo_type)
            policy_result = evaluate_scan_policy(result, fail_on=args.fail_on, policy=load_policy(args.policy)) if (args.fail_on or args.policy) else None
            if policy_result:
                result.metadata["policy"] = policy_result
            print_scan_result(result, as_json=args.json)
            if policy_result and not policy_result["ok"]:
                sys.exit(1)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    elif args.command == "compare":
        try:
            result = compare_resources(args.left, args.right, revision_left=args.revision_left,
                                       revision_right=args.revision_right, token=args.token,
                                       include_files=args.files, include_card=args.card,
                                       include_formats=args.formats, deep=args.deep)
            print_comparison(result, as_json=args.json)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    elif args.command == "get":
        try:
            resource_parts = list(args.resource)
            if len(resource_parts) == 2 and resource_parts[0] in {"hf", "ms", "github", "kaggle"} and args.source == "auto":
                args.source, resource = resource_parts
            elif len(resource_parts) == 1:
                resource = resource_parts[0]
            else:
                raise ValueError("Usage: modely get [--source SOURCE] RESOURCE or modely get SOURCE RESOURCE")
            result = download_resource(
                resource,
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
                profile=args.profile,
                endpoint=args.endpoint,
                max_workers=args.max_workers,
                timeout=args.timeout,
                retries=args.retries,
                checksum=args.checksum,
                resume=not args.no_resume,
            )
            if args.manifest:
                create_download_manifest(resource if "://" in resource else f"hf://models/{resource}", result,
                                         include=args.include, exclude=args.exclude,
                                         checksum=args.checksum, output=args.manifest)
            print(f"Downloaded to: {result}")
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    elif args.command == "sources":
        try:
            if args.sources_command == "list":
                print_source_profiles(list_source_profiles(args.source), as_json=args.json)
            elif args.sources_command == "probe":
                candidates = None if args.source == "all" else [args.source]
                print_probe_results(rank_sources(args.resource, candidates=candidates, timeout=args.timeout), as_json=args.json)
            else:
                print("Usage: modely sources [list|probe]")
                sys.exit(1)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    elif args.command == "capabilities":
        try:
            if args.backend:
                items = get_backend_capabilities(args.backend)
            else:
                items = list_backends()
                if args.source != "all":
                    items = [item for item in items if item.source == args.source]
            print_backend_capabilities(items, as_json=args.json)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    elif args.command == "login":
        token = sys.stdin.read().strip() if args.stdin else args.token
        if not token:
            print("Error: token is empty")
            sys.exit(1)
        save_token(args.source, token)
        if args.source == "kaggle":
            if getattr(args, "username", None):
                config = cache._load_config()
                config["kaggle_username"] = args.username
                cache._save_config(config)
                print("Kaggle credentials saved")
            elif not os.environ.get("KAGGLE_USERNAME"):
                print("Kaggle key saved. Set KAGGLE_USERNAME or configure ~/.kaggle/kaggle.json for Kaggle API authentication.")
            else:
                print("Kaggle key saved")
        else:
            print(f"Token saved for {args.source}")
    elif args.command == "logout":
        removed = delete_token(args.source)
        print(f"Token removed for {args.source}" if removed else f"No stored token for {args.source}")
    elif args.command == "whoami":
        print(whoami(args.source, args.token))
    elif args.command == "lock":
        try:
            manifest = create_lock(args.resource, revision=args.revision, include=args.include,
                                   exclude=args.exclude, output=args.output, token=args.token,
                                   profile=args.profile, endpoint=args.endpoint, alternatives=args.alternatives,
                                   strict=args.strict, require_checksums=args.require_checksums)
            if args.json:
                print(json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False))
            else:
                print(f"Wrote lockfile to: {args.output} ({len(manifest.files)} file(s))")
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    elif args.command == "install":
        try:
            result = install_lock(args.file, local_dir=args.local_dir, cache_dir=args.cache_dir,
                                  token=args.token, force_download=args.force_download,
                                  fallback=args.fallback, prefer=args.prefer)
            print(f"Installed to: {result}")
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    elif args.command == "validate-lock":
        try:
            result = validate_lock(args.file, local_dir=args.local_dir, checksum=args.checksum,
                                   strict=args.strict, require_checksums=args.require_checksums)
            print_lock_validation(result, as_json=args.json)
            if not result["ok"]:
                sys.exit(1)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    elif args.command == "catalog":
        try:
            if args.catalog_command == "scan":
                report = scan_catalog(args.root, cache_dir=args.cache_dir, from_cache=args.cache,
                                      include_scores=args.score, include_scan=args.scan,
                                      use_remote=args.remote, token=args.token, endpoint=args.endpoint)
                if args.scan and (args.fail_on or args.policy):
                    policy = load_policy(args.policy)
                    failed = False
                    for entry in report.entries:
                        if entry.scan and entry.local_path and not args.remote:
                            scan_result = scan_path(entry.local_path)
                            policy_result = evaluate_scan_policy(scan_result, fail_on=args.fail_on, policy=policy)
                            entry.scan["policy"] = policy_result
                            failed = failed or not policy_result["ok"]
                    report.metadata["policy_failed"] = failed
                else:
                    failed = False
                if args.snapshot:
                    report.metadata["snapshot"] = snapshot_catalog(report, history_dir=args.history_dir)
                if args.output:
                    write_catalog_report(report, args.output)
                print_catalog_report(report, as_json=args.json)
                if failed:
                    sys.exit(1)
            elif args.catalog_command == "diff":
                print_catalog_diff(diff_catalogs(read_catalog_report(args.left), read_catalog_report(args.right)), as_json=args.json)
            elif args.catalog_command == "export":
                exported = export_catalog(read_catalog_report(args.report), format=args.format)
                if args.output:
                    with open(args.output, "w") as f:
                        f.write(exported)
                else:
                    print(exported, end="")
            elif args.catalog_command == "history":
                snapshots = list_catalog_snapshots(args.dir)
                if args.json:
                    print(json.dumps(snapshots, indent=2, ensure_ascii=False))
                else:
                    if snapshots:
                        for item in snapshots:
                            print(f"{item['path']} ({item['size']} bytes)")
                    else:
                        print("No catalog snapshots found.")
            elif args.catalog_command == "gate":
                result = evaluate_catalog_policy(read_catalog_report(args.report), fail_on=args.fail_on, policy=load_policy(args.policy))
                print_catalog_policy_result(result, as_json=args.json)
                if not result["ok"]:
                    sys.exit(1)
            else:
                print("Usage: modely catalog [scan|diff|export|history]")
                sys.exit(1)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    elif args.command == "doctor":
        try:
            print_doctor_report(doctor_resource(args.query, source=args.source, repo_type=args.repo_type,
                                                strategy=args.strategy, probe=args.probe, limit=args.limit, threshold=args.threshold,
                                                token=args.token, endpoint=args.endpoint), as_json=args.json)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    elif args.command == "choose":
        try:
            print_choice(choose_resource(args.query, source=args.source, repo_type=args.repo_type,
                                         strategy=args.strategy, limit=args.limit, threshold=args.threshold,
                                         token=args.token, endpoint=args.endpoint), as_json=args.json)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    elif args.command == "verify-mirror":
        try:
            print_mirror_verification(verify_mirror(args.left, args.right, token=args.token, deep=not args.no_deep), as_json=args.json)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    elif args.command == "report":
        try:
            text = create_resource_report(args.resource, format=args.format, source=args.source, repo_type=args.repo_type)
            if args.output:
                with open(args.output, "w") as f:
                    f.write(text)
            else:
                print(text, end="")
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    elif args.command == "benchmark":
        try:
            candidates = None if args.sources == "all" else [s.strip() for s in args.sources.split(",") if s.strip()]
            print_benchmark_results(benchmark_sources(args.resource, candidates=candidates, url=args.url, timeout=args.timeout), as_json=args.json)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    elif args.command == "batch-download":
        try:
            plan = create_batch_download_plan(
                args.keyword,
                source=args.source,
                repo_type=args.repo_type,
                tags=args.tag,
                limit=args.limit,
                search_limit=args.search_limit,
                task=args.task,
                library=args.library,
                license=args.license,
                sort=args.sort,
                direction=args.direction,
                author=args.author,
                after=args.after,
                before=args.before,
                full=args.full,
            )
            if args.yes:
                result = run_batch_download(
                    plan,
                    local_dir=args.local_dir,
                    cache_dir=args.cache_dir,
                    token=args.token,
                    include=args.include,
                    exclude=args.exclude,
                    profile=args.profile,
                    prefer=args.prefer,
                    fallback=args.fallback,
                    force_download=args.force_download,
                    backend=args.backend,
                    with_lfs=args.with_lfs,
                    endpoint=args.endpoint,
                    max_workers=args.max_workers,
                    timeout=args.timeout,
                    retries=args.retries,
                    checksum=args.checksum,
                    resume=not args.no_resume,
                    fail_fast=args.fail_fast,
                )
                print_batch_download_result(result, as_json=args.json)
                if not result["ok"]:
                    sys.exit(1)
            else:
                print_batch_download_result(plan, as_json=args.json)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    elif args.command in {"sync", "mirror"}:
        try:
            result = sync_resource(args.resource, local_dir=args.local_dir, revision=args.revision,
                                   include=args.include, exclude=args.exclude, token=args.token,
                                   cache_dir=args.cache_dir, manifest=args.manifest,
                                   checksum=args.checksum, force_download=args.force_download,
                                   source=args.source, prefer=args.prefer, profile=args.profile,
                                   report=args.report, analyze=args.analyze,
                                   compare_to=args.compare_to, deep=args.deep)
            print(f"Synced to: {result}")
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    elif args.command == "cache":
        cache_main(args)
    elif args.command == "watch":
        watch_main(args)
    elif args.command == "resolve":
        try:
            result = resolve_resource(args.query, source=args.source, repo_type=args.repo_type,
                                      task=args.task, library=args.library, license=args.license,
                                      limit=args.limit, threshold=args.threshold, full=args.full)
            print_resolve_result(result, as_json=args.json)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
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
        dedupe_parser = subparsers.add_parser("dedupe")
        dedupe_parser.add_argument("--dry-run", action="store_true")
        dedupe_parser.add_argument("--json", action="store_true")
        serve_parser = subparsers.add_parser("serve")
        serve_parser.add_argument("--host", default="127.0.0.1")
        serve_parser.add_argument("--port", type=int, default=8765)
        serve_parser.add_argument("--open", action="store_true")

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

    elif args.cache_command == "dedupe":
        cache.print_dedupe_report(cache.find_duplicate_files(cache_dir), as_json=getattr(args, "json", False))

    elif args.cache_command == "serve":
        serve_cache_browser(
            cache_dir,
            host=getattr(args, "host", "127.0.0.1"),
            port=getattr(args, "port", 8765),
            open_browser=getattr(args, "open", False),
        )

    else:
        print("Usage: modely cache [info|list|clean|config|dedupe|serve]")
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
    "resolve_resource",
    "print_resolve_result",
    "score_resource",
    "print_asset_score",
    "scan_resource",
    "print_scan_result",
    "scan_catalog",
    "print_catalog_report",
]
