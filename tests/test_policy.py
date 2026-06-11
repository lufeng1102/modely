"""Unit tests for policy evaluation."""

from modely.policy import evaluate_scan_policy
from modely.types import AssetAnalysis, FileSummary, RepoInfo, ScanFinding, ScanResult


def _scan(findings, license="mit"):
    return ScanResult(
        "resource",
        "high" if any(f.severity == "high" for f in findings) else "low",
        findings=findings,
        analysis=AssetAnalysis(RepoInfo("hf", "model", "repo", license=license), FileSummary()),
    )


def test_fail_on_severity_threshold():
    result = evaluate_scan_policy(_scan([ScanFinding("x", "high", "security", "bad")]), fail_on="medium")

    assert result["ok"] is False
    assert result["violations"][0]["type"] == "severity"


def test_deny_and_ignore_finding_ids():
    scan = _scan([
        ScanFinding("remote-code", "medium", "security", "code"),
        ScanFinding("missing-checksums", "low", "reproducibility", "checksum"),
    ])

    result = evaluate_scan_policy(scan, policy={"deny_finding_ids": ["remote-code"], "ignore_finding_ids": ["missing-checksums"]})

    assert result["ok"] is False
    assert result["violations"][0]["type"] == "deny_finding"
    assert result["ignored"][0]["id"] == "missing-checksums"


def test_allowed_license_policy():
    result = evaluate_scan_policy(_scan([], license="unknown"), policy={"allow_licenses": ["mit", "apache-2.0"]})

    assert result["ok"] is False
    assert result["violations"][0]["type"] == "license"
