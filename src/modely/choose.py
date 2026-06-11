"""Cross-source choice helpers."""

from __future__ import annotations

import json
from typing import Optional

from .resolve import resolve_resource
from .scan import scan_resource
from .score import score_resource
from .sources import rank_sources
from .types import RepoRef
from .uri import format_modely_uri

_RISK_PENALTY = {"none": 0, "low": 5, "medium": 20, "high": 40}


def choose_resource(
    query: str,
    *,
    source: str = "all",
    repo_type: str = "model",
    strategy: str = "balanced",
    limit: int = 5,
    threshold: float = 0.35,
    token: Optional[str] = None,
    endpoint: Optional[str] = None,
) -> dict:
    """Choose the best candidate for a query using existing modely signals."""
    resolved = resolve_resource(query, source=source, repo_type=repo_type, limit=limit, threshold=threshold)
    warnings = list(resolved.warnings or [])
    probe_rank = {}
    if strategy == "fastest":
        try:
            probe_rank = {r.source: i for i, r in enumerate(rank_sources(query, candidates=None if source == "all" else [source])) if r.ok}
        except Exception as exc:
            warnings.append(f"probe failed: {exc}")

    candidates = []
    for candidate in resolved.candidates:
        uri = candidate.modely_uri or _candidate_uri(candidate)
        item = {
            "uri": uri,
            "source": candidate.source,
            "repo_id": candidate.repo_id,
            "confidence": candidate.confidence,
            "signals": candidate.signals,
            "score": None,
            "risk_level": None,
            "rank_score": candidate.confidence * 100,
            "reasons": list(candidate.signals),
            "warnings": [],
        }
        try:
            scored = score_resource(uri, token=token, endpoint=endpoint)
            item["score"] = scored.score
            item["rank_score"] += scored.score
            item["reasons"].append(f"score={scored.score}")
        except Exception as exc:
            item["warnings"].append(f"score failed: {exc}")
        try:
            scanned = scan_resource(uri, token=token, endpoint=endpoint)
            item["risk_level"] = scanned.risk_level
            penalty = _RISK_PENALTY.get(scanned.risk_level, 0)
            item["rank_score"] -= penalty
            item["reasons"].append(f"risk={scanned.risk_level}")
        except Exception as exc:
            item["warnings"].append(f"scan failed: {exc}")
        if strategy == "safest":
            item["rank_score"] -= _RISK_PENALTY.get(item["risk_level"], 0)
        elif strategy == "fastest" and item["source"] in probe_rank:
            item["rank_score"] += max(0, 50 - probe_rank[item["source"]] * 10)
            item["reasons"].append("fast-source")
        elif strategy == "freshest":
            item["rank_score"] += 5 if candidate.result.get("last_modified") else 0
        candidates.append(item)

    candidates.sort(key=lambda c: c["rank_score"], reverse=True)
    return {
        "query": query,
        "strategy": strategy,
        "recommended": candidates[0] if candidates else None,
        "candidates": candidates,
        "resolve": resolved.to_dict(),
        "warnings": warnings,
    }


def _candidate_uri(candidate) -> str:
    return format_modely_uri(RepoRef(candidate.source, candidate.repo_type, candidate.repo_id))


def print_choice(result: dict, *, as_json: bool = False) -> None:
    if as_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return
    print(f"Query:    {result['query']}")
    print(f"Strategy: {result['strategy']}")
    rec = result.get("recommended")
    if not rec:
        print("No candidate recommended.")
    else:
        print(f"Recommended: {rec['uri']}")
        print(f"Reason:      {', '.join(rec['reasons']) or '-'}")
    if result.get("warnings"):
        print("Warnings:")
        for warning in result["warnings"]:
            print(f"  - {warning}")
