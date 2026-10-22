"""Plausibility rules: range and jump checks on the values of one curve."""

from collections.abc import Iterable, Sequence
from datetime import date
from itertools import pairwise

from processing.domain.formatting import format_bp, format_yield
from processing.domain.quality import Finding, Rule, Severity, Value
from processing.domain.rule_config import CurveRules

# A jump is only checked against a previous value at most this many days back (user decision).
JUMP_LOOKBACK_DAYS = 31


def check_range(values: Iterable[Value], rules: CurveRules) -> list[Finding]:
    """Flag every value strictly below the range minimum or strictly above the maximum."""
    t = rules.thresholds
    findings: list[Finding] = []
    for value in values:
        if value.value < t.range_min or value.value > t.range_max:
            findings.append(
                Finding(
                    rule=Rule.RANGE,
                    severity=Severity.WARN,
                    valid_date=value.valid_date,
                    maturity=value.maturity,
                    version_id=value.version_id,
                    value=value.value,
                    explanation=rules.explanations.range_warn,
                    evidence=f"{format_yield(value.value)} on {value.valid_date}",
                )
            )
    return findings


def check_jumps(series: Sequence[Value], valid_from: date, rules: CurveRules) -> list[Finding]:
    """Flag the moves of one maturity against the previous value of the series.

    The series is sorted by date and may start before valid_from (lead-in). Only values from
    valid_from on are assessed. A value whose predecessor is more than JUMP_LOOKBACK_DAYS
    back is not assessed.
    """
    t = rules.thresholds
    findings: list[Finding] = []
    for previous, current in pairwise(series):
        if current.valid_date < valid_from:
            continue
        if (current.valid_date - previous.valid_date).days > JUMP_LOOKBACK_DAYS:
            continue
        delta_bp = (current.value - previous.value) * 100
        magnitude = abs(delta_bp)
        if magnitude > t.jump_warn_bp:
            severity, explanation = Severity.WARN, rules.explanations.jump_warn
        elif magnitude > t.jump_info_bp:
            severity, explanation = Severity.INFO, rules.explanations.jump_info
        else:
            continue
        findings.append(
            Finding(
                rule=Rule.JUMP,
                severity=severity,
                valid_date=current.valid_date,
                maturity=current.maturity,
                version_id=current.version_id,
                value=current.value,
                explanation=explanation,
                evidence=(
                    f"{format_yield(current.value)} on {current.valid_date} "
                    f"after {format_yield(previous.value)} on {previous.valid_date} "
                    f"({format_bp(float(delta_bp))})"
                ),
            )
        )
    return findings
