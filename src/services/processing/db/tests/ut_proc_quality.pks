create or replace package ut_proc_quality as
  --%suite(proc_quality: quality check storage and as-of reads)
  --%rollback(auto)

  --%test(The latest check run per day wins at the read as-of time)
  procedure latest_check_per_day_wins;

  --%test(A check recorded after the read as-of is hidden)
  procedure a_check_after_as_of_is_hidden;

  --%test(Recording the same natural key twice replaces one run)
  procedure record_check_twice_is_idempotent;

  --%test(The latest check run per curve reports its warn days)
  procedure latest_run_reports_warn_days;
end ut_proc_quality;
/
