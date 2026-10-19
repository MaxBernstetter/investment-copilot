--liquibase formatted sql

--changeset yieldlens:core_observation-spec runOnChange:true endDelimiter:/ stripComments:false
create or replace package core_observation authid definer as
  -- The PL/SQL interface of the bitemporal observation store.
  -- Callers never write the observation table directly.
  -- The caller owns the transaction: nothing here commits. A failed call
  -- leaves no trace of its batch (it rolls back to its own savepoint).

  -- Raised when a concurrent call opened the first version of an observation
  -- of the batch before this call could. Nothing of the batch is stored; retry.
  open_version_exists constant pls_integer := -20001;

  -- Raised when an observation appears more than once in the batch.
  -- Nothing of the batch is stored.
  duplicate_observation constant pls_integer := -20002;

  -- Raised when an observation names a curve without a definition, or a
  -- maturity that is not on its curve's grid. Nothing of the batch is stored.
  off_grid_observation constant pls_integer := -20003;

  -- known_to of the open (current) version.
  open_known_to constant timestamp := timestamp '9999-12-31 00:00:00';

  -- Records the observations of the batch as versions, never overwriting.
  -- Every observation must name a defined curve and a maturity on that
  -- curve's grid (tables curve and grid_maturity). Then, per observation:
  -- * no open version yet: the observation becomes a new open version;
  -- * open version with another value or source_id: it is closed at the call's
  --   knowledge time and the observation becomes the new open version;
  -- * open version with the same value and source_id: unchanged, nothing is
  --   written (run_id and change_reason describe the write, not the value).
  -- o_recorded_count counts the new versions only.
  -- All versions of one call share one knowledge time: p_known_from if given
  -- (for deterministic tests and replays), otherwise the database clock in UTC,
  -- read after the open versions of the batch are locked, so that concurrent
  -- writers of the same observations get increasing knowledge times.
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

  -- Fails when the batch names an observation more than once.
  procedure ensure_unique_observations(p_versions in observation_version_list_t) is
    l_duplicates pls_integer;
  begin
    select count(*)
      into l_duplicates
      from (
        select 1
          from table(p_versions)
         group by curve_id, maturity, valid_date, origin, method_version
        having count(*) > 1
      );
    if l_duplicates > 0 then
      raise_application_error(
        duplicate_observation,
        l_duplicates || ' observation(s) appear more than once in the batch'
      );
    end if;
  end ensure_unique_observations;

  -- Fails when the batch names an undefined curve or a maturity off its grid.
  procedure ensure_on_grid(p_versions in observation_version_list_t) is
    l_off_grid pls_integer;
  begin
    select count(*)
      into l_off_grid
      from table(p_versions) v
     where not exists (
       select 1
         from curve c
         join grid_maturity g on g.grid_version = c.grid_version
        where c.curve_id = v.curve_id
          and g.maturity = v.maturity
     );
    if l_off_grid > 0 then
      raise_application_error(
        off_grid_observation,
        l_off_grid || ' observation(s) name an undefined curve or a maturity off the curve''s grid'
      );
    end if;
  end ensure_on_grid;

  procedure record_versions(
    p_versions       in  observation_version_list_t,
    o_known_from     out timestamp,
    o_recorded_count out pls_integer,
    p_known_from     in  timestamp default null
  ) is
    l_known_from      timestamp(6);
    l_valid_date_from date;
    l_valid_date_to   date;

    -- The open versions of the batch's observations. Locking them serializes
    -- concurrent writers of the same observations.
    cursor c_open_versions is
      select o.version_id
        from observation o
       where o.known_to = open_known_to
         and o.valid_date between l_valid_date_from and l_valid_date_to
         and exists (
           select 1
             from table(p_versions) v
            where v.curve_id = o.curve_id
              and v.maturity = o.maturity
              and v.valid_date = o.valid_date
              and v.origin = o.origin
              and decode(v.method_version, o.method_version, 1, 0) = 1
         )
         for update;
  begin
    dbms_application_info.set_module('core_observation', 'record_versions');
    savepoint record_versions_start;
    ensure_unique_observations(p_versions);
    ensure_on_grid(p_versions);

    select min(valid_date), max(valid_date)
      into l_valid_date_from, l_valid_date_to
      from table(p_versions);

    open c_open_versions;
    close c_open_versions;
    l_known_from := coalesce(p_known_from, sys_extract_utc(systimestamp));

    -- Close every open version whose value or source changed.
    update observation o
       set o.known_to = l_known_from
     where o.known_to = open_known_to
       and o.valid_date between l_valid_date_from and l_valid_date_to
       and exists (
         select 1
           from table(p_versions) v
          where v.curve_id = o.curve_id
            and v.maturity = o.maturity
            and v.valid_date = o.valid_date
            and v.origin = o.origin
            and decode(v.method_version, o.method_version, 1, 0) = 1
            and (v.value <> o.value or decode(v.source_id, o.source_id, 1, 0) = 0)
       );

    -- Open a version for every observation that has none now: new ones and
    -- changed ones. Unchanged observations still have their open version.
    insert into observation (
      curve_id, maturity, valid_date, value, known_from,
      origin, method_version, source_id, run_id, change_reason
    )
    select v.curve_id, v.maturity, v.valid_date, v.value, l_known_from,
           v.origin, v.method_version, v.source_id, v.run_id, v.change_reason
      from table(p_versions) v
     where not exists (
       select 1
         from observation o
        where o.known_to = open_known_to
          and o.valid_date between l_valid_date_from and l_valid_date_to
          and o.curve_id = v.curve_id
          and o.maturity = v.maturity
          and o.valid_date = v.valid_date
          and o.origin = v.origin
          and decode(o.method_version, v.method_version, 1, 0) = 1
     );

    o_recorded_count := sql%rowcount;
    o_known_from := l_known_from;
    dbms_application_info.set_module(null, null);
  exception
    when dup_val_on_index then
      rollback to savepoint record_versions_start;
      dbms_application_info.set_module(null, null);
      raise_application_error(
        open_version_exists,
        'A concurrent call opened a version of an observation in the batch',
        true
      );
    when others then
      rollback to savepoint record_versions_start;
      dbms_application_info.set_module(null, null);
      raise;
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
