"""Asset analysis helpers."""

from __future__ import annotations

import json
from typing import Optional, List

from .card import get_card
from .files import classify_file, filter_files, format_file_size, list_repo_files, summarize_files
from .info import get_repo_info
from .profiles import resolve_download_profile
from .types import AssetAnalysis, FileInfo


def analyze_resource(
    resource: str,
    *,
    revision: Optional[str] = None,
    token: Optional[str] = None,
    endpoint: Optional[str] = None,
    include: Optional[List[str]] = None,
    exclude: Optional[List[str]] = None,
    profile: Optional[str] = None,
    top_files: int = 5,
) -> AssetAnalysis:
    """Analyze metadata, files, card presence, and weight formats for a resource."""
    warnings = []
    include, exclude = resolve_download_profile(profile, include, exclude)
    info = get_repo_info(resource, revision=revision, token=token, endpoint=endpoint)
    files = list_repo_files(resource, revision=revision, token=token, endpoint=endpoint)
    selected = filter_files(files, include, exclude)
    summary = summarize_files(files, include, exclude)
    largest_files = sorted(selected, key=lambda f: f.size or 0, reverse=True)[:top_files]
    categories = {classify_file(f.path) for f in selected}
    weight_formats = _weight_formats(selected)
    card = get_card(resource, revision=revision, token=token, endpoint=endpoint)
    has_config = "config" in categories
    has_tokenizer = "tokenizer" in categories
    has_card = bool(card.text) or "card" in categories
    if not files:
        warnings.append("No files listed")
    if not has_config:
        warnings.append("No config file detected")
    if not has_tokenizer:
        warnings.append("No tokenizer file detected")
    if not has_card:
        warnings.append("No model/dataset card detected")
    warnings.extend(card.warnings)
    return AssetAnalysis(
        info=info,
        summary=summary,
        files=selected,
        largest_files=largest_files,
        weight_formats=weight_formats,
        has_config=has_config,
        has_tokenizer=has_tokenizer,
        has_card=has_card,
        card=card,
        warnings=list(dict.fromkeys(warnings)),
        metadata={"profile": profile, "include": include, "exclude": exclude},
    )


def print_asset_analysis(analysis: AssetAnalysis, *, as_json: bool = False) -> None:
    """Print an asset analysis."""
    if as_json:
        print(json.dumps(analysis.to_dict(), indent=2, ensure_ascii=False))
        return
    info = analysis.info
    print(f"Source:        {info.source}")
    print(f"Repo type:     {info.repo_type}")
    print(f"Repo ID:       {info.repo_id}")
    if info.url:
        print(f"URL:           {info.url}")
    if info.license:
        print(f"License:       {info.license}")
    if info.tags:
        print(f"Tags:          {', '.join(info.tags[:20])}")
    print(f"Files:         {analysis.summary.selected_files}/{analysis.summary.total_files}")
    print(f"Size:          {format_file_size(analysis.summary.selected_size)} / {format_file_size(analysis.summary.total_size)}")
    print(f"Has config:    {analysis.has_config}")
    print(f"Has tokenizer: {analysis.has_tokenizer}")
    print(f"Has card:      {analysis.has_card}")
    if analysis.summary.categories:
        print("Categories:")
        for name in sorted(analysis.summary.categories):
            print(f"  - {name}: {analysis.summary.categories[name]} ({format_file_size(analysis.summary.category_sizes.get(name, 0))})")
    if analysis.weight_formats:
        print("Weight formats:")
        for name, count in sorted(analysis.weight_formats.items()):
            print(f"  - {name}: {count}")
    if analysis.largest_files:
        print("Largest files:")
        for f in analysis.largest_files:
            print(f"  - {f.path} ({format_file_size(f.size)})")
    if analysis.warnings:
        print("Warnings:")
        for warning in analysis.warnings:
            print(f"  - {warning}")


def _weight_formats(files: List[FileInfo]) -> dict:
    formats = {}
    for f in files:
        lower = f.path.lower()
        fmt = None
        for suffix in (".safetensors", ".gguf", ".bin", ".pt", ".pth", ".ckpt", ".onnx", ".h5", ".msgpack"):
            if lower.endswith(suffix):
                fmt = suffix.lstrip(".")
                break
        if fmt:
            formats[fmt] = formats.get(fmt, 0) + 1
    return formats
