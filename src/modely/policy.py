"""Policy evaluation helpers for scan results."""

from __future__ import annotations

import json
from typing import Optional

from .types import CatalogReport, ScanResult

_SEVERITY = {"low": 1, "medium": 2, "high": 3}


def load_policy(path: Optional[str]) -> dict:
    """Load a JSON policy file, returning an empty policy for None."""
    if not path:
        return {}
    with open(path, "r") as f:
        return json.load(f)


def evaluate_scan_policy(scan: ScanResult, *, fail_on: Optional[str] = None, policy: Optional[dict] = None) -> dict:
    """Evaluate a scan result against severity and finding/license policy."""
    policy = policy or {}
    threshold = fail_on or policy.get("fail_on")
    ignored_ids = set(policy.get("ignore_finding_ids") or [])
    deny_ids = set(policy.get("deny_finding_ids") or [])
    allow_licenses = {str(v).lower() for v in (policy.get("allow_licenses") or [])}
    violations = []
    ignored = []

    for finding in scan.findings:
        item = finding.to_dict()
        if finding.id in ignored_ids:
            ignored.append(item)
            continue
        if threshold and _SEVERITY.get(finding.severity, 0) >= _SEVERITY.get(threshold, 0):
            violations.append({"type": "severity", "finding": item, "threshold": threshold})
        if finding.id in deny_ids:
            violations.append({"type": "deny_finding", "finding": item})

    license_name = (scan.analysis.info.license if scan.analysis and scan.analysis.info else None) or ""
    if allow_licenses and license_name.lower() not in allow_licenses:
        violations.append({"type": "license", "license": license_name, "allowed": sorted(allow_licenses)})

    return {
        "ok": not violations,
        "fail_on": threshold,
        "violations": violations,
        "ignored": ignored,
    }


def evaluate_catalog_policy(report: CatalogReport, *, fail_on: Optional[str] = None, policy: Optional[dict] = None) -> dict:
    """Evaluate catalog entry scan summaries against policy."""
    policy = policy or {}
    threshold = fail_on or policy.get("fail_on")
    ignored_ids = set(policy.get("ignore_finding_ids") or [])
    deny_ids = set(policy.get("deny_finding_ids") or [])
    blocked = []
    allowed = []
    for entry in report.entries:
        scan = entry.scan or {}
        finding_ids = [fid for fid in scan.get("finding_ids", []) if fid not in ignored_ids]
        risk = _risk_from_finding_ids(finding_ids, scan.get("risk_level") or "none")
        violations = []
        if threshold and _SEVERITY.get(risk, 0) >= _SEVERITY.get(threshold, 0):
            violations.append({"type": "severity", "risk_level": risk, "threshold": threshold})
        for fid in finding_ids:
            if fid in deny_ids:
                violations.append({"type": "deny_finding", "finding_id": fid})
        item = {"id": entry.id, "repo_id": entry.repo_id, "local_path": entry.local_path, "risk_level": risk, "finding_ids": finding_ids, "violations": violations}
        if violations:
            blocked.append(item)
        else:
            allowed.append(item)
    return {"ok": not blocked, "fail_on": threshold, "blocked": blocked, "allowed": allowed, "summary": {"blocked": len(blocked), "allowed": len(allowed)}}


def _risk_from_finding_ids(finding_ids: list[str], fallback: str) -> str:
    if not finding_ids:
        return "none"
    if fallback == "high":
        return "high"
    if any(fid in {"missing-license", "pickle-artifact"} for fid in finding_ids):
        return "high"
    if any(fid in {"missing-card", "missing-config", "unsafe-weight-format", "remote-code", "large-weights", "missing-file-list"} for fid in finding_ids):
        return "medium"
    return fallback if fallback in _SEVERITY else "low"


def print_catalog_policy_result(result: dict, *, as_json: bool = False) -> None:
    """Print catalog policy gate results."""
    if as_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return
    print(f"Status:  {'ok' if result['ok'] else 'failed'}")
    print(f"Blocked: {result['summary']['blocked']}")
    print(f"Allowed: {result['summary']['allowed']}")
    if result["blocked"]:
        print("Blocked assets:")
        for item in result["blocked"]:
            label = item.get("repo_id") or item.get("id") or item.get("local_path")
            reasons = ", ".join(v["type"] for v in item["violations"])
            print(f"  - {label}: {reasons}")
