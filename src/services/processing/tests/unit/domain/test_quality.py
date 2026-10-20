from datetime import date

from processing.domain.quality import Finding, Rule, Severity, Status, worst


def finding(severity: Severity) -> Finding:
    return Finding(
        rule=Rule.JUMP,
        severity=severity,
        valid_date=date(2026, 10, 8),
        maturity="10Y",
        version_id=1,
        value=None,
        explanation="",
        evidence="",
    )


def test_worst_is_passed_without_findings() -> None:
    assert worst([]) is Status.PASSED


def test_worst_is_info_for_info_findings() -> None:
    assert worst([finding(Severity.INFO)]) is Status.INFO


def test_worst_warn_beats_info() -> None:
    assert worst([finding(Severity.INFO), finding(Severity.WARN)]) is Status.WARN
