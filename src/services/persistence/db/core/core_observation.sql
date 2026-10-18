--liquibase formatted sql

--changeset yieldlens:core_observation-spec runOnChange:true endDelimiter:/ stripComments:false
create or replace package core_observation authid definer as
  -- The PL/SQL interface of the bitemporal observation store.
  -- Callers never write the observation table directly.
  -- The caller owns the transaction: nothing here commits.

  -- Raised when an observation in the batch already has an open version
  -- (or appears twice in the batch). Closing versions belongs to versioning.
  open_version_exists constant pls_integer := -20001;

  -- known_to of the open (current) version.
  open_known_to constant timestamp := timestamp '9999-12-31 00:00:00';

  -- Records every observation of the batch as a new open version.
  -- All versions of one call share one knowledge time: p_known_from if given
  -- (for deterministic tests and replays), otherwise the database clock in UTC.
  procedure record_versions(
    p_versions       in  observation_version_list_t,
    o_known_from     out timestamp,
    o_recorded_count out pls_integer,
    p_known_from     in  timestamp default null
  );

  -- Every stored version of one curve in a valid-date range (inclusive),
  -- ordered by valid_date, maturity, origin, method_version and known_from.
  function get_versions(
    p_curve_id        in varchar2,
    p_valid_date_from in date,
    p_valid_date_to   in date
  ) return sys_refcursor;
end core_observation;
/

--changeset yieldlens:core_observation-body runOnChange:true endDelimiter:/ stripComments:false
create or replace package body core_observation as

  procedure record_versions(
    p_versions       in  observation_version_list_t,
    o_known_from     out timestamp,
    o_recorded_count out pls_integer,
    p_known_from     in  timestamp default null
  ) is
    l_known_from constant timestamp(6) := coalesce(p_known_from, sys_extract_utc(systimestamp));
  begin
    dbms_application_info.set_module('core_observation', 'record_versions');

    insert into observation (
      curve_id, maturity, valid_date, value, known_from,
      origin, method_version, source_id, run_id, change_reason
    )
    select v.curve_id, v.maturity, v.valid_date, v.value, l_known_from,
           v.origin, v.method_version, v.source_id, v.run_id, v.change_reason
      from table(p_versions) v;

    o_recorded_count := sql%rowcount;
    o_known_from := l_known_from;
    dbms_application_info.set_module(null, null);
  exception
    when dup_val_on_index then
      dbms_application_info.set_module(null, null);
      raise_application_error(
        open_version_exists,
        'An observation in the batch already has an open version',
        true
      );
  end record_versions;

  function get_versions(
    p_curve_id        in varchar2,
    p_valid_date_from in date,
    p_valid_date_to   in date
  ) return sys_refcursor is
    l_versions sys_refcursor;
  begin
    open l_versions for
      select version_id, curve_id, maturity, valid_date, value, known_from, known_to,
             origin, method_version, source_id, run_id, change_reason
        from observation
       where curve_id = p_curve_id
         and valid_date between p_valid_date_from and p_valid_date_to
       order by valid_date, maturity, origin, method_version, known_from;
    return l_versions;
  end get_versions;

end core_observation;
/
