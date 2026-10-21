create or replace package body ut_ing_run as

  c_jan_2001 constant timestamp := timestamp '2001-01-15 12:00:00';

  function stored(p_run_id in varchar2, p_attempt in pls_integer) return run%rowtype is
    l_row run%rowtype;
  begin
    select * into l_row from run where run_id = p_run_id and attempt = p_attempt;
    return l_row;
  end stored;

  procedure insert_ut_run(
    p_run_id    in varchar2,
    p_attempt   in pls_integer,
    p_operation in varchar2,
    p_status    in varchar2,
    p_started_at in timestamp,
    p_finished_at in timestamp default null,
    p_error_type in varchar2 default null
  ) is
  begin
    insert into run (
      run_id, attempt, operation, status, started_at, finished_at, error_type
    ) values (
      p_run_id, p_attempt, p_operation, p_status, p_started_at, p_finished_at, p_error_type
    );
  end insert_ut_run;

  procedure start_numbers_attempts_per_run is
  begin
    ut.expect(ing_run.start_run('run-a', 'daily')).to_equal(1);
    ut.expect(ing_run.start_run('run-a', 'daily')).to_equal(2);
    ut.expect(ing_run.start_run('run-b', 'history')).to_equal(1);
  end start_numbers_attempts_per_run;

  procedure start_records_a_running_attempt is
    l_row     run%rowtype;
    l_attempt pls_integer;
  begin
    l_attempt := ing_run.start_run('run-start', 'replay');
    l_row := stored('run-start', 1);

    ut.expect(l_row.status).to_equal('running');
    ut.expect(l_row.finished_at).to_be_null();
    ut.expect(l_row.delivered_count).to_equal(0);
    ut.expect(l_row.recorded_count).to_equal(0);
    ut.expect(l_row.unchanged_count).to_equal(0);
    ut.expect(l_row.started_at).not_to_be_null();
  end start_records_a_running_attempt;

  procedure start_rejects_an_unknown_operation is
    l_attempt pls_integer;
  begin
    l_attempt := ing_run.start_run('run-bad-op', 'scenario');
  end start_rejects_an_unknown_operation;

  procedure finish_records_status_counts_and_error is
    l_row     run%rowtype;
    l_attempt pls_integer;
  begin
    l_attempt := ing_run.start_run('run-finish', 'history');
    ing_run.finish_run(
      p_run_id          => 'run-finish',
      p_attempt         => 1,
      p_status          => 'partial',
      p_delivered_count => 66,
      p_recorded_count  => 66,
      p_unchanged_count => 0,
      p_error_type      => 'InvalidPayloadError',
      p_error_message   => 'bad csv'
    );
    l_row := stored('run-finish', 1);

    ut.expect(l_row.status).to_equal('partial');
    ut.expect(l_row.finished_at).not_to_be_null();
    ut.expect(l_row.delivered_count).to_equal(66);
    ut.expect(l_row.recorded_count).to_equal(66);
    ut.expect(l_row.unchanged_count).to_equal(0);
    ut.expect(l_row.error_type).to_equal('InvalidPayloadError');
    ut.expect(l_row.error_message).to_equal('bad csv');
  end finish_records_status_counts_and_error;

  procedure finish_keeps_the_first_outcome is
    l_row     run%rowtype;
    l_attempt pls_integer;
  begin
    l_attempt := ing_run.start_run('run-twice', 'daily');
    ing_run.finish_run('run-twice', 1, 'succeeded', 1, 1, 0);
    ing_run.finish_run(
      'run-twice', 1, 'failed', 0, 0, 0, p_error_type => 'PersistenceWriteError'
    );
    l_row := stored('run-twice', 1);

    ut.expect(l_row.status).to_equal('succeeded');
    ut.expect(l_row.error_type).to_be_null();
  end finish_keeps_the_first_outcome;

  procedure finish_rejects_running_as_outcome is
    l_attempt pls_integer;
  begin
    l_attempt := ing_run.start_run('run-bad-finish', 'daily');
    ing_run.finish_run('run-bad-finish', 1, 'running', 0, 0, 0);
  end finish_rejects_running_as_outcome;

  procedure finish_of_an_unknown_attempt_fails is
  begin
    ing_run.finish_run('run-missing', 9, 'succeeded', 0, 0, 0);
  end finish_of_an_unknown_attempt_fails;

  procedure a_failed_outcome_needs_an_error_type is
    l_attempt pls_integer;
  begin
    l_attempt := ing_run.start_run('run-no-error', 'daily');
    ing_run.finish_run('run-no-error', 1, 'failed', 0, 0, 0);
  end a_failed_outcome_needs_an_error_type;

  procedure fail_unfinished_marks_only_running_attempts is
    l_changed pls_integer;
    l_first   run%rowtype;
    l_second  run%rowtype;
    l_attempt pls_integer;
  begin
    l_attempt := ing_run.start_run('run-fail-open', 'daily');
    ing_run.finish_run('run-fail-open', 1, 'succeeded', 10, 10, 0);
    l_attempt := ing_run.start_run('run-fail-open', 'daily');

    l_changed := ing_run.fail_unfinished_run('run-fail-open', 'AttemptAbandoned', 'killed');
    l_first := stored('run-fail-open', 1);
    l_second := stored('run-fail-open', 2);

    ut.expect(l_changed).to_equal(1);
    ut.expect(l_first.status).to_equal('succeeded');
    ut.expect(l_second.status).to_equal('failed');
    ut.expect(l_second.error_type).to_equal('AttemptAbandoned');
  end fail_unfinished_marks_only_running_attempts;

  procedure fail_unfinished_twice_marks_none_the_second_time is
    l_first   pls_integer;
    l_second  pls_integer;
    l_row     run%rowtype;
    l_attempt pls_integer;
  begin
    l_attempt := ing_run.start_run('run-fail-twice', 'daily');
    l_first := ing_run.fail_unfinished_run('run-fail-twice', 'AttemptAbandoned');
    l_second := ing_run.fail_unfinished_run('run-fail-twice', 'OtherError');
    l_row := stored('run-fail-twice', 1);

    ut.expect(l_first).to_equal(1);
    ut.expect(l_second).to_equal(0);
    ut.expect(l_row.error_type).to_equal('AttemptAbandoned');
  end fail_unfinished_twice_marks_none_the_second_time;

  procedure get_runs_lists_newest_first_and_pages_before_an_attempt is
    l_cursor   sys_refcursor;
    l_row      run%rowtype;
    l_ids      sys.odcinumberlist := sys.odcinumberlist();
    l_oldest_id number;
    l_page2     sys.odcinumberlist := sys.odcinumberlist();
  begin
    insert_ut_run('ut-runs-a', 1, 'daily', 'succeeded', c_jan_2001, c_jan_2001, null);
    insert_ut_run('ut-runs-b', 1, 'daily', 'succeeded', c_jan_2001 + 1, c_jan_2001 + 1, null);
    insert_ut_run('ut-runs-c', 1, 'daily', 'succeeded', c_jan_2001 + 2, c_jan_2001 + 2, null);

    select attempt_id into l_oldest_id from run where run_id = 'ut-runs-a';

    l_cursor := ing_run.get_runs(
      p_started_from      => timestamp '2001-01-01 00:00:00',
      p_started_before    => timestamp '2001-02-01 00:00:00',
      p_limit             => 2
    );
    loop
      fetch l_cursor into l_row;
      exit when l_cursor%notfound;
      l_ids.extend;
      l_ids(l_ids.count) := l_row.attempt_id;
    end loop;
    close l_cursor;

    ut.expect(l_ids.count).to_equal(2);
    ut.expect(l_ids(1)).to_be_greater_than(l_ids(2));

    l_cursor := ing_run.get_runs(
      p_started_from      => timestamp '2001-01-01 00:00:00',
      p_started_before    => timestamp '2001-02-01 00:00:00',
      p_before_attempt_id => l_ids(2),
      p_limit             => 2
    );
    loop
      fetch l_cursor into l_row;
      exit when l_cursor%notfound;
      l_page2.extend;
      l_page2(l_page2.count) := l_row.attempt_id;
    end loop;
    close l_cursor;

    ut.expect(l_page2.count).to_equal(1);
    ut.expect(l_page2(1)).to_equal(l_oldest_id);
  end get_runs_lists_newest_first_and_pages_before_an_attempt;

  procedure get_runs_filters_by_start_time is
    l_cursor sys_refcursor;
    l_row    run%rowtype;
    l_count  pls_integer := 0;
  begin
    insert_ut_run('ut-filter-in', 1, 'daily', 'succeeded', timestamp '2001-01-10 00:00:00', timestamp '2001-01-10 00:00:00', null);
    insert_ut_run('ut-filter-out', 1, 'daily', 'succeeded', timestamp '2001-02-10 00:00:00', timestamp '2001-02-10 00:00:00', null);

    l_cursor := ing_run.get_runs(
      p_started_from   => timestamp '2001-01-01 00:00:00',
      p_started_before => timestamp '2001-02-01 00:00:00'
    );
    loop
      fetch l_cursor into l_row;
      exit when l_cursor%notfound;
      if l_row.run_id like 'ut-filter-%' then
        l_count := l_count + 1;
        ut.expect(l_row.run_id).to_equal('ut-filter-in');
      end if;
    end loop;
    close l_cursor;

    ut.expect(l_count).to_equal(1);
  end get_runs_filters_by_start_time;

  procedure get_run_lists_every_attempt_in_order is
    l_cursor sys_refcursor;
    l_row    run%rowtype;
    l_attempts sys.odcinumberlist := sys.odcinumberlist();
  begin
    insert_ut_run('ut-attempts', 1, 'daily', 'failed', c_jan_2001, c_jan_2001, 'E1');
    insert_ut_run('ut-attempts', 2, 'daily', 'succeeded', c_jan_2001 + 1, c_jan_2001 + 1, null);

    l_cursor := ing_run.get_run('ut-attempts');
    loop
      fetch l_cursor into l_row;
      exit when l_cursor%notfound;
      l_attempts.extend;
      l_attempts(l_attempts.count) := l_row.attempt;
    end loop;
    close l_cursor;

    ut.expect(anydata.convertcollection(l_attempts)).to_equal(
      anydata.convertcollection(sys.odcinumberlist(1, 2))
    );
  end get_run_lists_every_attempt_in_order;

  procedure get_alert_attempts_starts_after_the_last_success_before_the_window is
    l_cursor sys_refcursor;
    l_row    run%rowtype;
    l_seen   varchar2(4000);
  begin
    insert_ut_run('ut-alert-0', 1, 'history', 'succeeded', timestamp '2001-01-01 00:00:00', timestamp '2001-01-01 00:00:00', null);
    insert_ut_run('ut-alert-1', 1, 'history', 'failed', timestamp '2001-01-10 00:00:00', timestamp '2001-01-10 00:00:00', 'E');
    insert_ut_run('ut-alert-2', 1, 'history', 'running', timestamp '2001-01-11 00:00:00');
    insert_ut_run('ut-alert-3', 1, 'history', 'succeeded', timestamp '2001-01-20 00:00:00', timestamp '2001-01-20 00:00:00', null);
    insert_ut_run('ut-alert-4', 1, 'history', 'partial', timestamp '2001-01-21 00:00:00', timestamp '2001-01-21 00:00:00', 'E');

    l_cursor := ing_run.get_alert_attempts(c_jan_2001);
    loop
      fetch l_cursor into l_row;
      exit when l_cursor%notfound;
      if l_row.run_id like 'ut-alert-%' then
        l_seen := l_seen || l_row.run_id || ',';
      end if;
    end loop;
    close l_cursor;

    ut.expect(l_seen).to_equal('ut-alert-1,ut-alert-3,ut-alert-4,');
  end get_alert_attempts_starts_after_the_last_success_before_the_window;

end ut_ing_run;
/
