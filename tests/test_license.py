"""Unit tests for license risk helpers."""

from modely.license import classify_license


def test_classify_license_permissive():
    result = classify_license("apache-2.0")
    assert result["class"] == "permissive"
    assert result["risk"] == "low"


def test_classify_license_unknown_high_risk():
    result = classify_license(None)
    assert result["class"] == "unknown"
    assert result["risk"] == "high"


def test_classify_license_non_commercial_high_risk():
    result = classify_license("cc-by-nc-4.0")
    assert result["class"] == "non-commercial"
    assert result["risk"] == "high"
