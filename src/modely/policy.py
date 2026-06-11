"""Policy evaluation helpers for scan results."""

from __future__ import annotations

import json
from typing import Optional

from .types import ScanResult

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
