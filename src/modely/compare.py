"""Cross-resource comparison helpers."""

from __future__ import annotations

import json
from typing import Optional

from .analyze import analyze_resource
from .files import format_file_size
from .types import ComparisonResult


def compare_resources(
    left: str,
    right: str,
    *,
    revision_left: Optional[str] = None,
    revision_right: Optional[str] = None,
    token: Optional[str] = None,
    include_files: bool = False,
    include_card: bool = False,
    include_formats: bool = False,
    deep: bool = False,
) -> ComparisonResult:
    """Compare two resources by analyzing both sides."""
    left_analysis = analyze_resource(left, revision=revision_left, token=token, deep=deep)
    right_analysis = analyze_resource(right, revision=revision_right, token=token, deep=deep)
    left_tags = set(left_analysis.info.tags or [])
    right_tags = set(right_analysis.info.tags or [])
    size_delta = (left_analysis.summary.selected_size or 0) - (right_analysis.summary.selected_size or 0)
    file_count_delta = (left_analysis.summary.selected_files or 0) - (right_analysis.summary.selected_files or 0)
    warnings = [f"left: {w}" for w in left_analysis.warnings] + [f"right: {w}" for w in right_analysis.warnings]
    summary = {
        "left_id": left_analysis.info.repo_id,
        "right_id": right_analysis.info.repo_id,
        "left_source": left_analysis.info.source,
        "right_source": right_analysis.info.source,
    }
    if include_files:
        summary["files"] = _compare_files(left_analysis.files, right_analysis.files)
    if include_card:
        summary["card"] = _compare_cards(left_analysis, right_analysis)
    if include_formats or deep:
        summary["formats"] = _compare_formats(left_analysis, right_analysis, include_deep=deep)
    return ComparisonResult(
        left=left_analysis,
        right=right_analysis,
        same_license=(left_analysis.info.license or None) == (right_analysis.info.license or None),
        shared_tags=sorted(left_tags & right_tags),
        different_tags={"left_only": sorted(left_tags - right_tags), "right_only": sorted(right_tags - left_tags)},
        size_delta=size_delta,
        file_count_delta=file_count_delta,
        summary=summary,
        warnings=warnings,
    )


def print_comparison(result: ComparisonResult, *, as_json: bool = False) -> None:
    """Print a resource comparison."""
    if as_json:
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        return
    left = result.left
    right = result.right
    rows = [
        ("Source", left.info.source, right.info.source),
        ("Repo ID", left.info.repo_id, right.info.repo_id),
        ("License", left.info.license or "-", right.info.license or "-"),
        ("Downloads", str(left.info.downloads), str(right.info.downloads)),
        ("Likes/Stars", str(left.info.likes), str(right.info.likes)),
        ("Forks", str(left.info.forks), str(right.info.forks)),
        ("Files", str(left.summary.selected_files), str(right.summary.selected_files)),
        ("Size", format_file_size(left.summary.selected_size), format_file_size(right.summary.selected_size)),
        ("Weight formats", ", ".join(sorted(left.weight_formats)) or "-", ", ".join(sorted(right.weight_formats)) or "-"),
        ("Has config", str(left.has_config), str(right.has_config)),
        ("Has tokenizer", str(left.has_tokenizer), str(right.has_tokenizer)),
        ("Has card", str(left.has_card), str(right.has_card)),
    ]
    widths = [max(len(str(r[i])) for r in ([('Field', 'Left', 'Right')] + rows)) for i in range(3)]
    print("  ".join(v.ljust(widths[i]) for i, v in enumerate(("Field", "Left", "Right"))))
    print("  ".join("-" * w for w in widths))
    for row in rows:
        print("  ".join(str(v).ljust(widths[i]) for i, v in enumerate(row)))
    print(f"\nFile count delta: {result.file_count_delta}")
    print(f"Size delta:       {format_file_size(abs(result.size_delta))} ({'left larger' if result.size_delta > 0 else 'right larger' if result.size_delta < 0 else 'same'})")
    if result.shared_tags:
        print(f"Shared tags:      {', '.join(result.shared_tags[:20])}")
    _print_detail_summary(result.summary)
    if result.warnings:
        print("Warnings:")
        for warning in result.warnings:
            print(f"  - {warning}")


def _compare_files(left_files, right_files) -> dict:
    left_by_path = {f.path: f for f in left_files}
    right_by_path = {f.path: f for f in right_files}
    left_paths = set(left_by_path)
    right_paths = set(right_by_path)
    changed = []
    for path in sorted(left_paths & right_paths):
        left = left_by_path[path]
        right = right_by_path[path]
        if (left.size or 0) != (right.size or 0) or (left.sha256 and right.sha256 and left.sha256 != right.sha256):
            changed.append({
                "path": path,
                "left_size": left.size,
                "right_size": right.size,
                "left_sha256": left.sha256,
                "right_sha256": right.sha256,
            })
    return {
        "added_files": sorted(right_paths - left_paths),
        "removed_files": sorted(left_paths - right_paths),
        "common_files": len(left_paths & right_paths),
        "changed_size_files": changed,
    }


def _compare_cards(left, right) -> dict:
    left_norm = ((left.card.metadata or {}).get("normalized") if left.card else {}) or {}
    right_norm = ((right.card.metadata or {}).get("normalized") if right.card else {}) or {}
    left_keys = set(left_norm)
    right_keys = set(right_norm)
    return {
        "left_has_card": left.has_card,
        "right_has_card": right.has_card,
        "normalized_left": left_norm,
        "normalized_right": right_norm,
        "license_changed": (left.info.license or None) != (right.info.license or None),
        "shared_card_keys": sorted(left_keys & right_keys),
        "different_card_keys": {"left_only": sorted(left_keys - right_keys), "right_only": sorted(right_keys - left_keys)},
    }


def _compare_formats(left, right, *, include_deep: bool = False) -> dict:
    left_formats = left.weight_formats or {}
    right_formats = right.weight_formats or {}
    keys = sorted(set(left_formats) | set(right_formats))
    result = {
        "left_weight_formats": left_formats,
        "right_weight_formats": right_formats,
        "format_delta": {key: (left_formats.get(key, 0), right_formats.get(key, 0)) for key in keys if left_formats.get(key, 0) != right_formats.get(key, 0)},
    }
    if include_deep:
        result["left_deep"] = (left.metadata or {}).get("deep")
        result["right_deep"] = (right.metadata or {}).get("deep")
    return result


def _print_detail_summary(summary: dict) -> None:
    if "files" in summary:
        files = summary["files"]
        print("File diff:")
        print(f"  Added:        {len(files['added_files'])}")
        print(f"  Removed:      {len(files['removed_files'])}")
        print(f"  Common:       {files['common_files']}")
        print(f"  Size changed: {len(files['changed_size_files'])}")
    if "card" in summary:
        card = summary["card"]
        print("Card diff:")
        print(f"  License changed: {card['license_changed']}")
        if card["shared_card_keys"]:
            print(f"  Shared keys:      {', '.join(card['shared_card_keys'])}")
    if "formats" in summary:
        formats = summary["formats"]
        print("Format diff:")
        if formats["format_delta"]:
            for key, values in formats["format_delta"].items():
                print(f"  - {key}: {values[0]} vs {values[1]}")
        else:
            print("  No weight format differences")
