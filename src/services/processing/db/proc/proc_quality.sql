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
             recorded_at = sys_extract_utc(systimestamp)
       where check_run_id = l_check_run_id;

      delete from quality_finding where check_run_id = l_check_run_id;
      delete from value_quality where check_run_id = l_check_run_id;
      delete from checked_day where check_run_id = l_check_run_id;
    exception
      when no_data_found then
        insert into check_run (
          run_id, curve_id, valid_from, valid_to, checked_as_of, rule_set_version
        ) values (
          p_run_id, p_curve_id, p_valid_from, p_valid_to, p_checked_as_of, p_rule_set_version
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

end proc_quality;
/
--rollback drop package body proc_quality;
