from ingestion.domain.run import RunCounts, RunStatus, outcome_of


def test_no_error_is_succeeded() -> None:
    outcome = outcome_of(RunCounts(10, 8, 2), 1, None)

    assert outcome.status == RunStatus.SUCCEEDED
    assert outcome.counts == RunCounts(10, 8, 2)
    assert outcome.error_type is None


def test_an_error_before_any_step_is_failed() -> None:
    outcome = outcome_of(RunCounts(), 0, ValueError("too early"))

    assert outcome.status == RunStatus.FAILED
    assert outcome.counts == RunCounts()


def test_an_error_after_a_step_is_partial() -> None:
    outcome = outcome_of(RunCounts(66, 66, 0), 1, RuntimeError("later"))

    assert outcome.status == RunStatus.PARTIAL
    assert outcome.counts.delivered_count == 66


def test_the_outcome_names_the_error() -> None:
    outcome = outcome_of(RunCounts(), 0, ValueError("nope"))

    assert outcome.error_type == "ValueError"
    assert outcome.error_message == "nope"
