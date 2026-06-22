"""Policy evaluation helpers for scan results."""

from __future__ import annotations

import json
from typing import Optional

from .types import CatalogReport, ScanResult

_SEVERITY = {"low": 1, "medium": 2, "high": 3}
_POLICY_TEMPLATES = {
    "permissive": {
        "fail_on": "high",
        "deny_sources": [],
        "deny_licenses": [],
        "ignore_finding_ids": [],
    },
    "balanced": {
        "fail_on": "medium",
        "deny_licenses": ["unknown", "other"],
        "deny_finding_ids": ["pickle-artifact", "remote-code"],
        "min_score": 60,
    },
    "strict": {
        "fail_on": "low",
        "allow_licenses": ["apache-2.0", "mit", "bsd-3-clause"],
        "deny_finding_ids": ["pickle-artifact", "remote-code", "missing-license"],
        "require_checksums": True,
        "min_score": 80,
    },
}


def policy_template(name: str = "balanced") -> dict:
    """Return a built-in policy template."""
    if name not in _POLICY_TEMPLATES:
        raise ValueError(f"Unknown policy template: {name}")
    return json.loads(json.dumps(_POLICY_TEMPLATES[name]))


def write_policy_template(name: str, output: Optional[str] = None) -> dict:
    """Write or return a built-in policy template."""
    template = policy_template(name)
    if output:
        with open(output, "w") as f:
            json.dump(template, f, indent=2, ensure_ascii=False)
    return template


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
    deny_licenses = {str(v).lower() for v in (policy.get("deny_licenses") or [])}
    deny_sources = {str(v).lower() for v in (policy.get("deny_sources") or [])}
    require_checksums = bool(policy.get("require_checksums"))
    min_score = policy.get("min_score")
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
    if deny_licenses and license_name.lower() in deny_licenses:
        violations.append({"type": "deny_license", "license": license_name})
    source = (scan.analysis.info.source if scan.analysis and scan.analysis.info else "").lower()
    if deny_sources and source in deny_sources:
        violations.append({"type": "deny_source", "source": source})
    if require_checksums and scan.analysis and any(not f.sha256 for f in (scan.analysis.files or [])):
        violations.append({"type": "require_checksums"})
    score_value = (scan.metadata or {}).get("score")
    if min_score is not None and score_value is not None and score_value < min_score:
        violations.append({"type": "min_score", "score": score_value, "minimum": min_score})

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
    deny_sources = {str(v).lower() for v in (policy.get("deny_sources") or [])}
    min_score = policy.get("min_score")
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
        if deny_sources and (entry.source or "").lower() in deny_sources:
            violations.append({"type": "deny_source", "source": entry.source})
        score_value = (entry.score or {}).get("score") if isinstance(entry.score, dict) else None
        if min_score is not None and score_value is not None and score_value < min_score:
            violations.append({"type": "min_score", "score": score_value, "minimum": min_score})
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
