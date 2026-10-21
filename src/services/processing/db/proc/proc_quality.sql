--liquibase formatted sql

--changeset yieldlens:proc_quality-spec runOnChange:true endDelimiter:/ stripComments:false
create or replace package proc_quality authid definer as
  -- Stores the result of one quality check run. The natural key is
  -- (curve_id, valid_from, valid_to, checked_as_of). Recording the same key
  -- again replaces that run's children. The caller owns the transaction.

  procedure record_check(
    p_run_id           in  varchar2,
    p_curve_id         in  varchar2,
    p_valid_from       in  date,
    p_valid_to         in  date,
    p_checked_as_of    in  timestamp,
    p_rule_set_version in  varchar2,
    p_days             in  proc_day_status_list_t,
    p_values           in  proc_value_status_list_t,
    p_findings         in  proc_finding_list_t,
    p_check_run_id     out number
  );

  function get_checked_days(
    p_curve_id in varchar2,
    p_from     in date,
    p_to       in date,
    p_as_of    in timestamp
  ) return sys_refcursor;

  function get_findings(
    p_curve_id in varchar2,
    p_from     in date,
    p_to       in date,
    p_maturity in varchar2 default null,
    p_as_of    in timestamp
  ) return sys_refcursor;

  function get_value_quality(
    p_curve_id in varchar2,
    p_from     in date,
    p_to       in date,
    p_maturity in varchar2 default null,
    p_as_of    in timestamp
  ) return sys_refcursor;

  function latest_check_runs return sys_refcursor;

  -- Check runs newest first, optionally filtered by recorded_at and paged before check_run_id.
  -- attempt is the run's 1-based position within its run_id, by (recorded_at, check_run_id).
  function get_runs(
    p_recorded_from       in timestamp default null,
    p_recorded_before     in timestamp default null,
    p_before_check_run_id in number    default null,
    p_limit               in pls_integer default 51
  ) return sys_refcursor;

  -- Every check run of a run id, in attempt order.
  function get_run(p_run_id in varchar2) return sys_refcursor;

  function current_time return timestamp;
end proc_quality;
/
--rollback drop package proc_quality;

--changeset yieldlens:proc_quality-body runOnChange:true endDelimiter:/ stripComments:false
create or replace package body proc_quality as

  procedure record_check(
    p_run_id           in  varchar2,
    p_curve_id         in  varchar2,
    p_valid_from       in  date,
    p_valid_to         in  date,
    p_checked_as_of    in  timestamp,
    p_rule_set_version in  varchar2,
    p_days             in  proc_day_status_list_t,
    p_values           in  proc_value_status_list_t,
    p_findings         in  proc_finding_list_t,
    p_check_run_id     out number
  ) is
    l_check_run_id number;
    l_value_count  number := p_values.count;
  begin
    dbms_application_info.set_module('proc_quality', 'record_check');

    begin
      select check_run_id
        into l_check_run_id
        from check_run
       where curve_id = p_curve_id
         and valid_from = p_valid_from
         and valid_to = p_valid_to
         and checked_as_of = p_checked_as_of
         for update;

      update check_run
         set run_id = p_run_id,
             rule_set_version = p_rule_set_version,
             recorded_at = sys_extract_utc(systimestamp),
             value_count = l_value_count
       where check_run_id = l_check_run_id;

      delete from quality_finding where check_run_id = l_check_run_id;
      delete from value_quality where check_run_id = l_check_run_id;
      delete from checked_day where check_run_id = l_check_run_id;
    exception
      when no_data_found then
        insert into check_run (
          run_id, curve_id, valid_from, valid_to, checked_as_of, rule_set_version, value_count
        ) values (
          p_run_id, p_curve_id, p_valid_from, p_valid_to, p_checked_as_of, p_rule_set_version,
          l_value_count
        )
        returning check_run_id into l_check_run_id;
    end;

    insert into checked_day (check_run_id, curve_id, valid_date, status)
    select l_check_run_id, p_curve_id, d.valid_date, d.status
      from table(p_days) d;

    insert into value_quality (check_run_id, version_id, curve_id, maturity, valid_date, status)
    select l_check_run_id, v.version_id, p_curve_id, v.maturity, v.valid_date, v.status
      from table(p_values) v;

    insert into quality_finding (
      check_run_id, curve_id, valid_date, maturity, version_id,
      rule, severity, value, explanation, evidence
    )
    select
      l_check_run_id, p_curve_id, f.valid_date, f.maturity, f.version_id,
      f.rule, f.severity, f.value, f.explanation, f.evidence
      from table(p_findings) f;

    p_check_run_id := l_check_run_id;
  end record_check;

  function get_checked_days(
    p_curve_id in varchar2,
    p_from     in date,
    p_to       in date,
    p_as_of    in timestamp
  ) return sys_refcursor is
    l_result sys_refcursor;
  begin
    dbms_application_info.set_module('proc_quality', 'get_checked_days');
    open l_result for
      with latest as (
        select cd.valid_date,
               max(cd.check_run_id) keep (dense_rank last order by r.checked_as_of, r.check_run_id)
                 as check_run_id
          from checked_day cd
          join check_run r on r.check_run_id = cd.check_run_id
         where cd.curve_id = p_curve_id
           and cd.valid_date between p_from and p_to
           and r.checked_as_of <= p_as_of
         group by cd.valid_date
      )
      select cd.valid_date, cd.status, r.run_id, r.checked_as_of
        from latest l
        join checked_day cd
          on cd.check_run_id = l.check_run_id and cd.valid_date = l.valid_date
        join check_run r on r.check_run_id = l.check_run_id
       order by cd.valid_date;
    return l_result;
  end get_checked_days;

  function get_findings(
    p_curve_id in varchar2,
    p_from     in date,
    p_to       in date,
    p_maturity in varchar2 default null,
    p_as_of    in timestamp
  ) return sys_refcursor is
    l_result sys_refcursor;
  begin
    dbms_application_info.set_module('proc_quality', 'get_findings');
    open l_result for
      with latest as (
        select cd.valid_date,
               max(cd.check_run_id) keep (dense_rank last order by r.checked_as_of, r.check_run_id)
                 as check_run_id
          from checked_day cd
          join check_run r on r.check_run_id = cd.check_run_id
         where cd.curve_id = p_curve_id
           and cd.valid_date between p_from and p_to
           and r.checked_as_of <= p_as_of
         group by cd.valid_date
      )
      select f.rule, f.severity, f.valid_date, f.maturity, f.version_id, f.value,
             f.explanation, f.evidence
        from latest l
        join quality_finding f
          on f.check_run_id = l.check_run_id and f.valid_date = l.valid_date
       where f.curve_id = p_curve_id
         and (p_maturity is null or f.maturity = p_maturity)
       order by f.valid_date, f.maturity nulls first, f.rule;
    return l_result;
  end get_findings;

  function get_value_quality(
    p_curve_id in varchar2,
    p_from     in date,
    p_to       in date,
    p_maturity in varchar2 default null,
    p_as_of    in timestamp
  ) return sys_refcursor is
    l_result sys_refcursor;
  begin
    dbms_application_info.set_module('proc_quality', 'get_value_quality');
    open l_result for
      with latest as (
        select cd.valid_date,
               max(cd.check_run_id) keep (dense_rank last order by r.checked_as_of, r.check_run_id)
                 as check_run_id
          from checked_day cd
          join check_run r on r.check_run_id = cd.check_run_id
         where cd.curve_id = p_curve_id
           and cd.valid_date between p_from and p_to
           and r.checked_as_of <= p_as_of
         group by cd.valid_date
      )
      select vq.version_id, vq.maturity, vq.valid_date, vq.status
        from latest l
        join value_quality vq
          on vq.check_run_id = l.check_run_id and vq.valid_date = l.valid_date
       where vq.curve_id = p_curve_id
         and (p_maturity is null or vq.maturity = p_maturity)
       order by vq.valid_date, vq.maturity;
    return l_result;
  end get_value_quality;

  function latest_check_runs return sys_refcursor is
    l_result sys_refcursor;
  begin
    dbms_application_info.set_module('proc_quality', 'latest_check_runs');
    open l_result for
      select curve_id, recorded_at, warn_days
        from (
          select r.curve_id,
                 r.recorded_at,
                 (select count(*)
                    from checked_day d
                   where d.check_run_id = r.check_run_id
                     and d.status = 'warn') as warn_days,
                 row_number() over (
                   partition by r.curve_id
                   order by r.recorded_at desc, r.check_run_id desc
                 ) as rn
            from check_run r
        )
       where rn = 1
       order by curve_id;
    return l_result;
  end latest_check_runs;

  function get_runs(
    p_recorded_from       in timestamp default null,
    p_recorded_before     in timestamp default null,
    p_before_check_run_id in number    default null,
    p_limit               in pls_integer default 51
  ) return sys_refcursor is
    l_runs sys_refcursor;
  begin
    dbms_application_info.set_module('proc_quality', 'get_runs');
    open l_runs for
      with page as (
        select r.check_run_id, r.run_id, r.recorded_at, r.value_count
          from check_run r
         where (p_recorded_from is null or r.recorded_at >= p_recorded_from)
           and (p_recorded_before is null or r.recorded_at < p_recorded_before)
           and (p_before_check_run_id is null or r.check_run_id < p_before_check_run_id)
         order by r.check_run_id desc
         fetch first p_limit rows only
      )
      select p.check_run_id, p.run_id,
             (select count(*)
                from check_run s
               where s.run_id = p.run_id
                 and (s.recorded_at < p.recorded_at
                      or (s.recorded_at = p.recorded_at and s.check_run_id <= p.check_run_id))
             ) as attempt,
             p.recorded_at, p.value_count
        from page p
       order by p.check_run_id desc;
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
    dbms_application_info.set_module('proc_quality', 'get_run');
    open l_run for
      select r.check_run_id, r.run_id,
             row_number() over (order by r.recorded_at, r.check_run_id) as attempt,
             r.recorded_at, r.value_count
        from check_run r
       where r.run_id = p_run_id
       order by r.recorded_at, r.check_run_id;
    dbms_application_info.set_module(null, null);
    return l_run;
  exception
    when others then
      dbms_application_info.set_module(null, null);
      raise;
  end get_run;

  function current_time return timestamp is
  begin
    return sys_extract_utc(systimestamp);
  end current_time;

end proc_quality;
/
--rollback drop package body proc_quality;
