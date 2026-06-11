"""Mirror verification helpers."""

from __future__ import annotations

import json

from .compare import compare_resources


def verify_mirror(left: str, right: str, *, token=None, deep: bool = True) -> dict:
    """Verify whether two resources appear to be equivalent mirrors."""
    comparison = compare_resources(left, right, token=token, include_files=True, include_card=True, include_formats=True, deep=deep)
    files = comparison.summary.get("files") or {}
    card = comparison.summary.get("card") or {}
    formats = comparison.summary.get("formats") or {}
    drift_reasons = []
    if files.get("added_files"):
        drift_reasons.append("right has extra files")
    if files.get("removed_files"):
        drift_reasons.append("right is missing files")
    if files.get("changed_size_files"):
        drift_reasons.append("common files differ")
    if card.get("license_changed"):
        drift_reasons.append("license differs")
    if formats.get("format_delta"):
        drift_reasons.append("weight formats differ")
    status = "drifted" if drift_reasons else "ok"
    return {
        "status": status,
        "left": left,
        "right": right,
        "reasons": drift_reasons,
        "comparison": comparison.to_dict(),
        "recommendations": _mirror_recommendations(drift_reasons),
    }


def print_mirror_verification(result: dict, *, as_json: bool = False) -> None:
    if as_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return
    print(f"Mirror status: {result['status']}")
    print(f"Left:          {result['left']}")
    print(f"Right:         {result['right']}")
    if result["reasons"]:
        print("Drift reasons:")
        for reason in result["reasons"]:
            print(f"  - {reason}")
    for rec in result.get("recommendations") or []:
        print(f"Recommendation: {rec}")


def _mirror_recommendations(reasons: list[str]) -> list[str]:
    if not reasons:
        return ["resources appear mirror-equivalent by selected checks"]
    return ["review differences before treating these resources as interchangeable"]
