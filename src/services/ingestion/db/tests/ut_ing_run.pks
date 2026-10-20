create or replace package ut_ing_run as
  --%suite(ing_run: run history)
  --%rollback(auto)

  --%test(Numbers attempts from one per run id)
  procedure start_numbers_attempts_per_run;

  --%test(Records a running attempt with zero counts)
  procedure start_records_a_running_attempt;

  --%test(Rejects an unknown operation)
  --%throws(-2290)
  procedure start_rejects_an_unknown_operation;

  --%test(Records status, counts and error on finish)
  procedure finish_records_status_counts_and_error;

  --%test(Keeps the first finish outcome)
  procedure finish_keeps_the_first_outcome;

  --%test(Rejects running as a finish status)
  --%throws(-20002)
  procedure finish_rejects_running_as_outcome;

  --%test(Fails when the attempt does not exist)
  --%throws(-20001)
  procedure finish_of_an_unknown_attempt_fails;

  --%test(Requires an error type for a failed outcome)
  --%throws(-2290)
  procedure a_failed_outcome_needs_an_error_type;

  --%test(Marks only running attempts failed)
  procedure fail_unfinished_marks_only_running_attempts;

  --%test(Changes nothing on a second fail_unfinished call)
  procedure fail_unfinished_twice_marks_none_the_second_time;

  --%test(Lists runs newest first and pages before an attempt id)
  procedure get_runs_lists_newest_first_and_pages_before_an_attempt;

  --%test(Filters runs by start time)
  procedure get_runs_filters_by_start_time;

  --%test(Lists every attempt of a run in attempt order)
  procedure get_run_lists_every_attempt_in_order;
end ut_ing_run;
/
