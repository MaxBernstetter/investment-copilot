"""Plausibility rules: range and jump checks on the values of one curve."""

from collections.abc import Iterable, Sequence
from datetime import date
from itertools import pairwise

from processing.domain.explanations import JUMP_INFO, JUMP_WARN, RANGE_WARN
from processing.domain.quality import Finding, Rule, Severity, Value
from processing.domain.rule_config import PlausibilityThresholds

# A jump is only checked against a previous value at most this many days back (user decision).
JUMP_LOOKBACK_DAYS = 31


def check_range(values: Iterable[Value], t: PlausibilityThresholds) -> list[Finding]:
    """Flag every value strictly below the range minimum or strictly above the maximum."""
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
                    explanation=RANGE_WARN,
                    evidence=f"{value.value:.2f} % on {value.valid_date}",
                )
            )
    return findings


def check_jumps(
    series: Sequence[Value], valid_from: date, t: PlausibilityThresholds
) -> list[Finding]:
    """Flag the moves of one maturity against the previous value of the series.

    The series is sorted by date and may start before valid_from (lead-in). Only values from
    valid_from on are assessed. A value whose predecessor is more than JUMP_LOOKBACK_DAYS
    back is not assessed.
    """
    findings: list[Finding] = []
    for previous, current in pairwise(series):
        if current.valid_date < valid_from:
            continue
        if (current.valid_date - previous.valid_date).days > JUMP_LOOKBACK_DAYS:
            continue
        delta_bp = (current.value - previous.value) * 100
        magnitude = abs(delta_bp)
        if magnitude > t.jump_warn_bp:
            severity, explanation = Severity.WARN, JUMP_WARN
        elif magnitude > t.jump_info_bp:
            severity, explanation = Severity.INFO, JUMP_INFO
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
                    f"{current.value:.2f} % on {current.valid_date} "
                    f"after {previous.value:.2f} % on {previous.valid_date} "
                    f"({delta_bp:+.1f} bp)"
                ),
            )
        )
    return findings
