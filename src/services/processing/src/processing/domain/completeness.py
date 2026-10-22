"""Completeness rules: missing dates and missing maturities on the curve's business days."""

from collections import defaultdict
from collections.abc import Iterable, Sequence
from datetime import date

from processing.domain.explanations import MISSING_DATE, MISSING_MATURITY
from processing.domain.quality import Finding, Rule, Severity, Value
from processing.domain.rule_config import CurveRules


def check_completeness(
    values: Iterable[Value],
    business_days: Sequence[date],
    rules: CurveRules,
) -> list[Finding]:
    """Flag business days with no values or with missing expected maturities."""
    by_date: dict[date, set[str]] = defaultdict(set)
    for value in values:
        by_date[value.valid_date].add(value.maturity)

    findings: list[Finding] = []
    for day in business_days:
        present = by_date.get(day, set())
        if not present:
            findings.append(
                Finding(
                    rule=Rule.MISSING_DATE,
                    severity=Severity.WARN,
                    valid_date=day,
                    maturity=None,
                    version_id=None,
                    value=None,
                    explanation=MISSING_DATE,
                    evidence=f"No value for any maturity on {day}",
                )
            )
            continue
        for maturity in rules.maturities_on(day):
            if maturity not in present:
                findings.append(
                    Finding(
                        rule=Rule.MISSING_MATURITY,
                        severity=Severity.WARN,
                        valid_date=day,
                        maturity=maturity,
                        version_id=None,
                        value=None,
                        explanation=MISSING_MATURITY,
                        evidence=f"No {maturity} value on {day}",
                    )
                )
    return findings
