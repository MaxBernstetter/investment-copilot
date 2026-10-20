from typing import Any

import pytest
from pydantic import ValidationError

from contracts.processing.v1 import (
    Finding,
    QualityDay,
    QualityStatus,
    Rule,
    RuleOutcome,
    Severity,
)


def quality_day(**overrides: Any) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "valid_date": "2026-10-07",
        "status": "warn",
        "run_id": "check-quality-ecb-aaa-spot-2026-10-07-2026-10-07",
        "checked_as_of": "2026-10-08T06:00:00Z",
        "rules": [{"rule": "missing-date", "outcome": "warn", "finding_count": 1}],
        "findings": [
            {
                "rule": "missing-date",
                "severity": "warn",
                "maturity": None,
                "version_id": None,
                "value": None,
                "explanation": "No value was published for this TARGET business day.",
                "evidence": "No value for any maturity on 2026-10-07",
            }
        ],
    }
    return fields | overrides


def test_quality_statuses() -> None:
    assert {status.value for status in QualityStatus} == {
        "passed",
        "info",
        "warn",
        "unchecked",
    }


def test_severity_is_warn_or_info() -> None:
    assert {severity.value for severity in Severity} == {"warn", "info"}


def test_a_quality_day_round_trips_json() -> None:
    day = QualityDay.model_validate(quality_day())

    assert day.rules == [
        RuleOutcome(rule=Rule.MISSING_DATE, outcome=QualityStatus.WARN, finding_count=1)
    ]
    assert day.findings[0] == Finding(
        rule=Rule.MISSING_DATE,
        severity=Severity.WARN,
        explanation="No value was published for this TARGET business day.",
        evidence="No value for any maturity on 2026-10-07",
    )
    assert QualityDay.model_validate_json(day.model_dump_json()) == day


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        QualityDay.model_validate(quality_day(extra="not in the contract"))

    with pytest.raises(ValidationError):
        Finding.model_validate(
            {
                "rule": "range",
                "severity": "warn",
                "explanation": "e",
                "evidence": "v",
                "unexpected": 1,
            }
        )
