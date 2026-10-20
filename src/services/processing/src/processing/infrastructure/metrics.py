"""Metrics of the quality check job: instrument names are the Prometheus names.

Counters carry no unit; the duration histogram is in seconds. Labels are the curve, the
worst day status, the rule and the severity. The job records one check per invocation that
passed curve validation: a finished check (``checked``) or a failed one (``failed``).
"""

from opentelemetry.metrics import Counter, Histogram, Meter

from processing.application.check_quality import CheckSummary

QUALITY_CHECKS = "yl_processing_quality_checks_total"
QUALITY_FINDINGS = "yl_processing_quality_findings_total"
VALUES_CHECKED = "yl_processing_values_checked_total"
CHECK_DURATION = "yl_processing_quality_check_duration_seconds"

HISTOGRAMS = (CHECK_DURATION,)
METRIC_NAMES: tuple[str, ...] = (QUALITY_CHECKS, QUALITY_FINDINGS, VALUES_CHECKED, CHECK_DURATION)

DURATION_BUCKETS_SECONDS = (0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120, 300)


class JobMetrics:
    def __init__(self, meter: Meter) -> None:
        self._checks: Counter = meter.create_counter(QUALITY_CHECKS, unit="")
        self._findings: Counter = meter.create_counter(QUALITY_FINDINGS, unit="")
        self._values: Counter = meter.create_counter(VALUES_CHECKED, unit="")
        self._duration: Histogram = meter.create_histogram(
            CHECK_DURATION,
            unit="s",
            explicit_bucket_boundaries_advisory=DURATION_BUCKETS_SECONDS,
        )

    def checked(self, summary: CheckSummary, duration_seconds: float) -> None:
        curve = summary.curve_id
        self._checks.add(1, {"curve": curve, "status": summary.worst_status.value})
        for finding in summary.finding_counts:
            self._findings.add(
                finding.count,
                {
                    "curve": curve,
                    "rule": finding.rule.value,
                    "severity": finding.severity.value,
                },
            )
        self._values.add(summary.values, {"curve": curve})
        self._duration.record(duration_seconds, {"curve": curve})

    def failed(self, curve_id: str, duration_seconds: float) -> None:
        self._checks.add(1, {"curve": curve_id, "status": "failed"})
        self._duration.record(duration_seconds, {"curve": curve_id})
