--liquibase formatted sql

--changeset yieldlens:ing_run-spec runOnChange:true endDelimiter:/ stripComments:false
create or replace package ing_run authid definer as
  -- The PL/SQL interface of the ingestion run history store.
  -- Callers never write the run table directly.
  -- The caller owns the transaction: nothing here commits.

  -- Records a new running attempt for a run id and returns its attempt number.
  function start_run(
    p_run_id    in varchar2,
    p_operation in varchar2
  ) return run.attempt%type;

  -- Records the outcome of an attempt. A second finish is a no-op (first outcome wins).
  procedure finish_run(
    p_run_id          in varchar2,
    p_attempt         in pls_integer,
    p_status          in varchar2,
    p_delivered_count in pls_integer,
    p_recorded_count  in pls_integer,
    p_unchanged_count in pls_integer,
    p_error_type      in varchar2 default null,
    p_error_message   in varchar2 default null
  );

  -- Marks every running attempt of a run id failed; returns how many rows changed.
  function fail_unfinished_run(
    p_run_id        in varchar2,
    p_error_type    in varchar2,
    p_error_message in varchar2 default null
  ) return pls_integer;

  -- Attempts newest first, optionally filtered by started_at and paged before attempt_id.
  function get_runs(
    p_started_from       in timestamp default null,
    p_started_before     in timestamp default null,
    p_before_attempt_id  in number   default null,
    p_limit              in pls_integer default 51
  ) return sys_refcursor;

  -- Every attempt of a run id, in attempt order.
  function get_run(p_run_id in varchar2) return sys_refcursor;
end ing_run;
/

--changeset yieldlens:ing_run-body runOnChange:true endDelimiter:/ stripComments:false
create or replace package body ing_run as

  function start_run(
    p_run_id    in varchar2,
    p_operation in varchar2
  ) return run.attempt%type is
    l_attempt run.attempt%type;
  begin
    dbms_application_info.set_module('ing_run', 'start_run');
    select nvl(max(attempt), 0) + 1 into l_attempt from run where run_id = p_run_id;
    insert into run (run_id, attempt, operation, status)
    values (p_run_id, l_attempt, p_operation, 'running');
    dbms_application_info.set_module(null, null);
    return l_attempt;
  exception
    when others then
      dbms_application_info.set_module(null, null);
      raise;
  end start_run;

  procedure finish_run(
    p_run_id          in varchar2,
    p_attempt         in pls_integer,
    p_status          in varchar2,
    p_delivered_count in pls_integer,
    p_recorded_count  in pls_integer,
    p_unchanged_count in pls_integer,
    p_error_type      in varchar2 default null,
    p_error_message   in varchar2 default null
  ) is
    l_status run.status%type;
  begin
    dbms_application_info.set_module('ing_run', 'finish_run');
    if p_status not in ('succeeded', 'partial', 'failed') then
      raise_application_error(-20002, 'finish_run: status must be succeeded, partial or failed: ' || p_status);
    end if;

    select status into l_status
      from run
     where run_id = p_run_id
       and attempt = p_attempt
       for update;

    if l_status = 'running' then
      update run
         set status = p_status,
             finished_at = sys_extract_utc(systimestamp),
             delivered_count = p_delivered_count,
             recorded_count = p_recorded_count,
             unchanged_count = p_unchanged_count,
             error_type = p_error_type,
             error_message = p_error_message
       where run_id = p_run_id
         and attempt = p_attempt;
    end if;
    dbms_application_info.set_module(null, null);
  exception
    when no_data_found then
      dbms_application_info.set_module(null, null);
      raise_application_error(-20001, 'finish_run: no attempt ' || p_attempt || ' of run ' || p_run_id);
    when others then
      dbms_application_info.set_module(null, null);
      raise;
  end finish_run;

  function fail_unfinished_run(
    p_run_id        in varchar2,
    p_error_type    in varchar2,
    p_error_message in varchar2 default null
  ) return pls_integer is
    l_changed pls_integer;
  begin
    dbms_application_info.set_module('ing_run', 'fail_unfinished_run');
    update run
       set status = 'failed',
           finished_at = sys_extract_utc(systimestamp),
           error_type = p_error_type,
           error_message = p_error_message
     where run_id = p_run_id
       and status = 'running';
    l_changed := sql%rowcount;
    dbms_application_info.set_module(null, null);
    return l_changed;
  exception
    when others then
      dbms_application_info.set_module(null, null);
      raise;
  end fail_unfinished_run;

  function get_runs(
    p_started_from       in timestamp default null,
    p_started_before     in timestamp default null,
    p_before_attempt_id  in number   default null,
    p_limit              in pls_integer default 51
  ) return sys_refcursor is
    l_runs sys_refcursor;
  begin
    dbms_application_info.set_module('ing_run', 'get_runs');
    open l_runs for
      select attempt_id, run_id, attempt, operation, status, started_at, finished_at,
             delivered_count, recorded_count, unchanged_count, error_type, error_message
        from run
       where (p_started_from is null or started_at >= p_started_from)
         and (p_started_before is null or started_at < p_started_before)
         and (p_before_attempt_id is null or attempt_id < p_before_attempt_id)
       order by attempt_id desc
       fetch first p_limit rows only;
    dbms_application_info.set_module(null, null);
    return l_runs;
  exception
    when others then
      dbms_application_info.set_module(null, null);
      raise;
  end get_runs;

  function get_run(p_run_id in varchar2) return sys_refcursor is
    l_run sys_refcursor;
  begin
    dbms_application_info.set_module('ing_run', 'get_run');
    open l_run for
      select attempt_id, run_id, attempt, operation, status, started_at, finished_at,
             delivered_count, recorded_count, unchanged_count, error_type, error_message
        from run
       where run_id = p_run_id
       order by attempt;
    dbms_application_info.set_module(null, null);
    return l_run;
  exception
    when others then
      dbms_application_info.set_module(null, null);
      raise;
  end get_run;

end ing_run;
/
