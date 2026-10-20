create or replace package body ut_proc_quality as

  c_curve constant varchar2(64) := 'ecb-aaa-spot-sim';
  c_from  constant date := date '2026-10-07';
  c_to    constant date := date '2026-10-07';
  c_day   constant date := date '2026-10-07';
  c_t1    constant timestamp := timestamp '2026-10-09 08:00:00';
  c_t2    constant timestamp := timestamp '2026-10-09 09:00:00';

  function empty_findings return proc_finding_list_t is
    l_list proc_finding_list_t := proc_finding_list_t();
  begin
    return l_list;
  end empty_findings;

  procedure record_day(
    p_run_id        in varchar2,
    p_checked_as_of in timestamp,
    p_status        in varchar2,
    p_version_id    in number default null,
    p_value_status  in varchar2 default null
  ) is
    l_check_run_id number;
    l_days proc_day_status_list_t := proc_day_status_list_t(
      proc_day_status_t(c_day, p_status)
    );
    l_values proc_value_status_list_t := proc_value_status_list_t();
    l_value_status varchar2(8 char) := coalesce(p_value_status, p_status);
  begin
    if p_version_id is not null then
      l_values.extend;
      l_values(1) := proc_value_status_t(p_version_id, '10Y', c_day, l_value_status);
    end if;

    proc_quality.record_check(
      p_run_id           => p_run_id,
      p_curve_id         => c_curve,
      p_valid_from       => c_from,
      p_valid_to         => c_to,
      p_checked_as_of    => p_checked_as_of,
      p_rule_set_version => '1',
      p_days             => l_days,
      p_values           => l_values,
      p_findings         => empty_findings(),
      p_check_run_id     => l_check_run_id
    );
  end record_day;

  function day_status(p_as_of in timestamp) return varchar2 is
    l_cursor sys_refcursor;
    l_valid_date date;
    l_status varchar2(8 char);
    l_run_id varchar2(128 char);
    l_checked_as_of timestamp;
  begin
    l_cursor := proc_quality.get_checked_days(c_curve, c_from, c_to, p_as_of);
    fetch l_cursor into l_valid_date, l_status, l_run_id, l_checked_as_of;
    if l_cursor%notfound then
      close l_cursor;
      return null;
    end if;
    close l_cursor;
    return l_status;
  end day_status;

  procedure latest_check_per_day_wins is
    l_cursor sys_refcursor;
    l_valid_date date;
    l_status     varchar2(8 char);
    l_run_id     varchar2(128 char);
    l_checked_as_of timestamp;
  begin
    record_day('run-early', c_t1, 'warn', 1, 'warn');
    record_day('run-late', c_t2, 'passed', 1, 'passed');

    l_cursor := proc_quality.get_checked_days(c_curve, c_from, c_to, c_t1 + interval '30' minute);
    fetch l_cursor into l_valid_date, l_status, l_run_id, l_checked_as_of;
    ut.expect(l_status).to_equal('warn');
    ut.expect(l_run_id).to_equal('run-early');
    close l_cursor;

    l_cursor := proc_quality.get_checked_days(c_curve, c_from, c_to, c_t2);
    fetch l_cursor into l_valid_date, l_status, l_run_id, l_checked_as_of;
    ut.expect(l_status).to_equal('passed');
    ut.expect(l_run_id).to_equal('run-late');
    close l_cursor;
  end latest_check_per_day_wins;

  procedure a_check_after_as_of_is_hidden is
    l_cursor sys_refcursor;
    l_valid_date date;
    l_status     varchar2(8 char);
    l_run_id     varchar2(128 char);
    l_checked_as_of timestamp;
  begin
    record_day('run-future', c_t2, 'warn');

    l_cursor := proc_quality.get_checked_days(c_curve, c_from, c_to, c_t1);
    fetch l_cursor into l_valid_date, l_status, l_run_id, l_checked_as_of;
    ut.expect(l_cursor%notfound).to_be_true();
    close l_cursor;
  end a_check_after_as_of_is_hidden;

  procedure record_check_twice_is_idempotent is
    l_count_before number;
    l_count_after  number;
  begin
    record_day('run-once', c_t1, 'warn');
    select count(*) into l_count_before from check_run where curve_id = c_curve;

    record_day('run-twice', c_t1, 'passed');

    select count(*) into l_count_after from check_run where curve_id = c_curve;
    ut.expect(l_count_after).to_equal(l_count_before);

    ut.expect(day_status(c_t1)).to_equal('passed');
  end record_check_twice_is_idempotent;

  function latest_warn_days return number is
    l_cursor sys_refcursor;
    l_curve_id varchar2(64 char);
    l_recorded_at timestamp;
    l_warn_days number;
    l_result number;
  begin
    l_cursor := proc_quality.latest_check_runs;
    loop
      fetch l_cursor into l_curve_id, l_recorded_at, l_warn_days;
      exit when l_cursor%notfound;
      if l_curve_id = c_curve then
        l_result := l_warn_days;
      end if;
    end loop;
    close l_cursor;
    return l_result;
  end latest_warn_days;

  procedure latest_run_reports_warn_days is
  begin
    record_day('run-warn', c_t1, 'warn');
    ut.expect(latest_warn_days()).to_equal(1);

    record_day('run-passed', c_t2, 'passed');
    ut.expect(latest_warn_days()).to_equal(0);
  end latest_run_reports_warn_days;

end ut_proc_quality;
/
