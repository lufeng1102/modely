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
) -> ComparisonResult:
    """Compare two resources by analyzing both sides."""
    left_analysis = analyze_resource(left, revision=revision_left, token=token)
    right_analysis = analyze_resource(right, revision=revision_right, token=token)
    left_tags = set(left_analysis.info.tags or [])
    right_tags = set(right_analysis.info.tags or [])
    size_delta = (left_analysis.summary.selected_size or 0) - (right_analysis.summary.selected_size or 0)
    file_count_delta = (left_analysis.summary.selected_files or 0) - (right_analysis.summary.selected_files or 0)
    warnings = [f"left: {w}" for w in left_analysis.warnings] + [f"right: {w}" for w in right_analysis.warnings]
    return ComparisonResult(
        left=left_analysis,
        right=right_analysis,
        same_license=(left_analysis.info.license or None) == (right_analysis.info.license or None),
        shared_tags=sorted(left_tags & right_tags),
        different_tags={"left_only": sorted(left_tags - right_tags), "right_only": sorted(right_tags - left_tags)},
        size_delta=size_delta,
        file_count_delta=file_count_delta,
        summary={
            "left_id": left_analysis.info.repo_id,
            "right_id": right_analysis.info.repo_id,
            "left_source": left_analysis.info.source,
            "right_source": right_analysis.info.source,
        },
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
    if result.warnings:
        print("Warnings:")
        for warning in result.warnings:
            print(f"  - {warning}")
