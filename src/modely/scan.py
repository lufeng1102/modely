"""Metadata-only asset risk scanning helpers."""

from __future__ import annotations

import json
from typing import List, Optional

from .analyze import analyze_resource
from .files import format_file_size
from .types import AssetAnalysis, ScanFinding, ScanResult

_PICKLE_SUFFIXES = (".pkl", ".pickle")
_RISKY_WEIGHT_SUFFIXES = (".pt", ".pth", ".bin", ".ckpt")
_CUSTOM_CODE_PREFIXES = ("modeling_", "configuration_", "tokenization_")
_SCRIPT_SUFFIXES = (".sh", ".bat", ".ps1")
_SEVERITY_ORDER = {"none": 0, "low": 1, "medium": 2, "high": 3}


def scan_resource(
    resource: str,
    *,
    revision: Optional[str] = None,
    token: Optional[str] = None,
    endpoint: Optional[str] = None,
    include: Optional[List[str]] = None,
    exclude: Optional[List[str]] = None,
    profile: Optional[str] = None,
    deep: bool = True,
) -> ScanResult:
    """Scan a resource for metadata, safety, and reproducibility risks."""
    analysis = analyze_resource(
        resource,
        revision=revision,
        token=token,
        endpoint=endpoint,
        include=include,
        exclude=exclude,
        profile=profile,
        deep=deep,
    )
    findings = find_scan_findings(analysis)
    return ScanResult(
        resource=resource,
        risk_level=risk_level(findings),
        findings=findings,
        summary=summarize_findings(findings),
        analysis=analysis,
        metadata={"deep": deep, "profile": profile, "include": include, "exclude": exclude},
    )


def find_scan_findings(analysis: AssetAnalysis) -> list[ScanFinding]:
    """Return deterministic scan findings for an analyzed asset."""
    findings: list[ScanFinding] = []
    info = analysis.info

    if not info.license:
        findings.append(ScanFinding(
            "missing-license",
            "high",
            "compliance",
            "No license metadata detected.",
            recommendation="Confirm usage rights before using this asset commercially.",
        ))
    if not analysis.has_card:
        findings.append(ScanFinding(
            "missing-card",
            "medium",
            "metadata",
            "No README/model card detected.",
            recommendation="Prefer assets with model cards that document intended use and limitations.",
        ))
    if not analysis.has_config:
        findings.append(ScanFinding(
            "missing-config",
            "medium",
            "completeness",
            "No config file detected.",
            recommendation="Verify the asset can be loaded by the intended framework.",
        ))
    if info.repo_type == "model" and not analysis.has_tokenizer:
        findings.append(ScanFinding(
            "missing-tokenizer",
            "low",
            "completeness",
            "No tokenizer file detected for this model.",
            recommendation="Check whether tokenizer assets are stored separately or are not required.",
        ))

    files = analysis.files or []
    if not files:
        findings.append(ScanFinding(
            "missing-file-list",
            "medium",
            "reproducibility",
            "No remote files were listed for this asset.",
            recommendation="Verify source permissions or backend file-listing support.",
        ))
    elif not any(f.sha256 for f in files):
        findings.append(ScanFinding(
            "missing-checksums",
            "low",
            "reproducibility",
            "No SHA256 metadata detected on listed files.",
            recommendation="Use source revisions and lockfiles; checksum validation may be unavailable.",
        ))

    for f in files:
        lower = f.path.lower()
        name = lower.rsplit("/", 1)[-1]
        if lower.endswith(_PICKLE_SUFFIXES):
            findings.append(ScanFinding(
                "pickle-artifact",
                "high",
                "security",
                "Pickle-like artifact may execute code when loaded.",
                path=f.path,
                recommendation="Avoid loading pickle artifacts from untrusted sources.",
            ))
        elif lower.endswith(_RISKY_WEIGHT_SUFFIXES):
            findings.append(ScanFinding(
                "unsafe-weight-format",
                "medium",
                "security",
                "Legacy weight format may execute code or be harder to inspect safely.",
                path=f.path,
                recommendation="Prefer safetensors when available.",
            ))

        if _is_custom_code_path(f.path):
            findings.append(ScanFinding(
                "remote-code",
                "medium",
                "security",
                "Custom Python code detected in the repository.",
                path=f.path,
                recommendation="Inspect code before enabling trust_remote_code or importing repository modules.",
            ))
        if name.endswith(_SCRIPT_SUFFIXES):
            findings.append(ScanFinding(
                "script-file",
                "low",
                "security",
                "Executable script detected in the repository.",
                path=f.path,
                recommendation="Review scripts before execution.",
            ))

    deep = (analysis.metadata or {}).get("deep") or {}
    if "large-weights" in deep.get("risk_flags", []) or deep.get("weight_bytes", 0) >= 10_000_000_000:
        findings.append(ScanFinding(
            "large-weights",
            "medium",
            "operations",
            f"Large weight files detected ({format_file_size(deep.get('weight_bytes', 0))}).",
            recommendation="Use profiles, partial downloads, or sufficient local storage.",
        ))

    return _dedupe_findings(findings)


def risk_level(findings: list[ScanFinding]) -> str:
    """Return overall risk level for findings."""
    if any(f.severity == "high" for f in findings):
        return "high"
    if any(f.severity == "medium" for f in findings):
        return "medium"
    if any(f.severity == "low" for f in findings):
        return "low"
    return "none"


def summarize_findings(findings: list[ScanFinding]) -> dict[str, int]:
    """Summarize findings by severity."""
    summary = {"high": 0, "medium": 0, "low": 0, "total": len(findings)}
    for finding in findings:
        if finding.severity in summary:
            summary[finding.severity] += 1
    return summary


def print_scan_result(result: ScanResult, *, as_json: bool = False) -> None:
    """Print a scan result."""
    if as_json:
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        return
    print(f"Resource:   {result.resource}")
    print(f"Risk level: {result.risk_level}")
    print(f"Findings:   {result.summary.get('total', 0)}")
    if not result.findings:
        print("No findings.")
        return
    print("Findings:")
    for finding in result.findings:
        location = f" ({finding.path})" if finding.path else ""
        print(f"  - [{finding.severity}] {finding.id}{location}: {finding.message}")
        if finding.recommendation:
            print(f"    Recommendation: {finding.recommendation}")


def _is_custom_code_path(path: str) -> bool:
    name = path.lower().rsplit("/", 1)[-1]
    if not name.endswith(".py"):
        return False
    if name.startswith(_CUSTOM_CODE_PREFIXES):
        return True
    return "/" not in path and name not in {"setup.py", "__init__.py"}


def _dedupe_findings(findings: list[ScanFinding]) -> list[ScanFinding]:
    seen = set()
    output = []
    for finding in findings:
        key = (finding.id, finding.path)
        if key in seen:
            continue
        seen.add(key)
        output.append(finding)
    return sorted(output, key=lambda f: (-_SEVERITY_ORDER.get(f.severity, 0), f.category, f.id, f.path or ""))
