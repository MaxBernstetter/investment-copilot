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

  -- Raised when a given knowledge time is not after the committed knowledge
  -- horizon. Nothing of the batch is stored.
  knowledge_time_not_increasing constant pls_integer := -20004;

  -- Raised when an observation of a simulated curve has a source other than
  -- 'scenario', or an observation with source 'scenario' names a real curve.
  -- Nothing of the batch is stored.
  simulated_mismatch constant pls_integer := -20005;

  -- known_to of the open (current) version.
  open_known_to constant timestamp := timestamp '9999-12-31 00:00:00';

  -- Records the observations of the batch as versions, never overwriting.
  -- Every observation must name a defined curve and a maturity on that
  -- curve's grid (tables curve and grid_maturity). Then, per observation:
  -- * no open version yet: the observation becomes a new open version;
  -- * open version with another value or source_id: it is closed at the call's
  --   knowledge time and the observation becomes the new open version;
  -- * open version with the same value and source_id: unchanged, nothing is
  --   written (run_id, change_reason, normalization_version and delivery_id
  --   describe how the value was written, not the value).
  -- A new version keeps its change_reason, except that an 'initial' version of
  -- an observation that already has a version is stored as 'revision'.
  -- correction, recalculation and simulated are stored as sent.
  -- Simulated curves take only source 'scenario' and vice versa (-20005).
  -- o_recorded_count counts the new versions only.
  -- All versions of one call share one knowledge time. Every call first locks
  -- the single row of table knowledge_clock, which serializes all writers, and
  -- reads the knowledge horizon (the knowledge time of the latest committed call).
  -- The knowledge time is p_known_from if given (for deterministic tests and
  -- replays; it must be after the horizon, else -20004), otherwise the database
  -- clock in UTC, moved forward to one microsecond after the horizon if the
  -- clock lags behind it. Knowledge times therefore strictly increase by commit
  -- order, and an as-of read at or before the horizon never changes later.
  -- The call moves the horizon to its knowledge time when it stores its batch.
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

  -- The published value of every maturity on the curve's grid, as known at
  -- p_as_of for one valid date: a version is visible when
  -- known_from <= p_as_of < known_to. Columns maturity, months, value; one row
  -- per grid maturity ordered by months, value null where no version is
  -- visible. No rows for an undefined curve.
  function get_as_of(
    p_curve_id   in varchar2,
    p_valid_date in date,
    p_as_of      in timestamp
  ) return sys_refcursor;

  -- The published values of one maturity over a range of valid dates (inclusive),
  -- as known at p_as_of. Columns valid_date, value; one row per valid date that
  -- has a visible published version, ordered by valid_date. Dates without one
  -- have no row.
  function get_series(
    p_curve_id   in varchar2,
    p_maturity   in varchar2,
    p_from       in date,
    p_to         in date,
    p_as_of      in timestamp
  ) return sys_refcursor;

  -- The published versions of one value (curve, maturity, valid date) known at
  -- p_as_of, oldest first by known_from. Versions known after p_as_of are left
  -- out; known_to is null for a version still current at p_as_of (closed later).
  -- Derived values are not included. No rows for an unknown value.
  function get_value_versions(
    p_curve_id   in varchar2,
    p_maturity   in varchar2,
    p_valid_date in date,
    p_as_of      in timestamp
  ) return sys_refcursor;

  -- The published values that differ between two knowledge states of one curve,
  -- for valid dates in a range (inclusive). Compares the state known at p_since
  -- with the state known at p_as_of; both are as-of reads, so a value is in
  -- either state when its knowledge interval contains the time.
  -- Insert-only means every value known at p_since still has a visible version
  -- at a later p_as_of; a value changed and changed back shows old = new with its
  -- latest reason. Values known only at p_as_of come with old_value null.
  -- Columns valid_date, maturity, old_value, new_value, change_reason, source_id,
  -- known_from (of the version visible at p_as_of); ordered by valid_date and the
  -- grid order of the maturity. Derived values and undefined curves are not included.
  function get_changes(
    p_curve_id in varchar2,
    p_from     in date,
    p_to       in date,
    p_since    in timestamp,
    p_as_of    in timestamp
  ) return sys_refcursor;

  -- 1 if the maturity is on the grid of the curve, else 0 (also 0 for an undefined curve).
  function has_maturity(
    p_curve_id in varchar2,
    p_maturity in varchar2
  ) return number;

  -- 1 if the curve is defined, else 0.
  function has_curve(
    p_curve_id in varchar2
  ) return number;

  -- The latest valid date with a published value visible at p_as_of; null if none.
  function latest_valid_date(
    p_curve_id in varchar2,
    p_as_of    in timestamp
  ) return date;

  -- The knowledge time now: the database clock in UTC. It is not the knowledge
  -- time a write would get; see record_versions. Use knowledge_horizon for
  -- the latest committed knowledge time.
  function current_knowledge_time return timestamp;

  -- The knowledge horizon: the knowledge time of the latest committed call of
  -- record_versions (1970-01-01 before the first one). Reads at or before it are
  -- safe watermarks: no later commit adds a version known at or before it.
  -- Does not lock; it sees the committed horizon of other sessions.
  function knowledge_horizon return timestamp;
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

  -- Fails when the batch mixes simulated and real data: a simulated curve takes
  -- only source 'scenario', and source 'scenario' only simulated curves.
  procedure ensure_isolated(p_versions in observation_version_list_t) is
    l_mixed pls_integer;
  begin
    select count(*)
      into l_mixed
      from table(p_versions) v
      join curve c on c.curve_id = v.curve_id
     where case when c.simulated = 'Y' then 1 else 0 end
           <> case when nvl(v.source_id, '-') = 'scenario' then 1 else 0 end;
    if l_mixed > 0 then
      raise_application_error(
        simulated_mismatch,
        l_mixed || ' observation(s) mix simulated and real data (simulated curves take only source scenario)'
      );
    end if;
  end ensure_isolated;

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
    l_horizon         timestamp(6);
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
    ensure_isolated(p_versions);

    -- Every writer locks the clock first, so knowledge times follow commit order.
    select known_until
      into l_horizon
      from knowledge_clock
     where clock_id = 1
       for update;

    select min(valid_date), max(valid_date)
      into l_valid_date_from, l_valid_date_to
      from table(p_versions);

    open c_open_versions;
    close c_open_versions;

    if p_known_from is null then
      l_known_from := greatest(
        sys_extract_utc(systimestamp),
        l_horizon + interval '0.000001' second
      );
    elsif p_known_from <= l_horizon then
      raise_application_error(
        knowledge_time_not_increasing,
        'Knowledge time ' || to_char(p_known_from, 'YYYY-MM-DD HH24:MI:SS.FF6')
          || ' is not after the knowledge horizon ' || to_char(l_horizon, 'YYYY-MM-DD HH24:MI:SS.FF6')
      );
    else
      l_known_from := p_known_from;
    end if;

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
    -- An 'initial' version of an observation that already has a version
    -- (closed or open) is a revision.
    insert into observation (
      curve_id, maturity, valid_date, value, known_from,
      origin, method_version, source_id, run_id, change_reason, normalization_version,
      delivery_id
    )
    select v.curve_id, v.maturity, v.valid_date, v.value, l_known_from,
           v.origin, v.method_version, v.source_id, v.run_id,
           case when v.change_reason = 'initial' and exists (
                  select 1
                    from observation p
                   where p.curve_id = v.curve_id
                     and p.maturity = v.maturity
                     and p.valid_date = v.valid_date
                     and p.origin = v.origin
                     and decode(p.method_version, v.method_version, 1, 0) = 1
                     and p.valid_date between l_valid_date_from and l_valid_date_to
                ) then 'revision'
                else v.change_reason
           end,
           v.normalization_version, v.delivery_id
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

    -- Move the horizon to this call's knowledge time (rolled back with the batch on failure).
    update knowledge_clock
       set known_until = l_known_from
     where clock_id = 1;

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
             origin, method_version, source_id, run_id, change_reason, normalization_version,
             delivery_id
        from observation
       where curve_id = p_curve_id
         and valid_date between p_valid_date_from and p_valid_date_to
       order by valid_date, maturity, origin, method_version, known_from;
    return l_versions;
  end get_versions;

  function get_as_of(
    p_curve_id   in varchar2,
    p_valid_date in date,
    p_as_of      in timestamp
  ) return sys_refcursor is
    l_points sys_refcursor;
  begin
    open l_points for
      select g.maturity, g.months, o.value
        from curve c
        join grid_maturity g on g.grid_version = c.grid_version
        left join observation o
          on o.curve_id = c.curve_id and o.maturity = g.maturity
         and o.valid_date = p_valid_date and o.origin = 'published'
         and o.known_from <= p_as_of and p_as_of < o.known_to
       where c.curve_id = p_curve_id
       order by g.months;
    return l_points;
  end get_as_of;

  function get_series(
    p_curve_id   in varchar2,
    p_maturity   in varchar2,
    p_from       in date,
    p_to         in date,
    p_as_of      in timestamp
  ) return sys_refcursor is
    l_points sys_refcursor;
  begin
    open l_points for
      select o.valid_date, o.value
        from observation o
       where o.curve_id = p_curve_id
         and o.maturity = p_maturity
         and o.origin = 'published'
         and o.valid_date between p_from and p_to
         and o.known_from <= p_as_of and p_as_of < o.known_to
       order by o.valid_date;
    return l_points;
  end get_series;

  function get_value_versions(
    p_curve_id   in varchar2,
    p_maturity   in varchar2,
    p_valid_date in date,
    p_as_of      in timestamp
  ) return sys_refcursor is
    l_versions sys_refcursor;
  begin
    open l_versions for
      select version_id, value, known_from,
             case when known_to > p_as_of then null else known_to end known_to,
             source_id, run_id, change_reason, normalization_version, delivery_id
        from observation
       where curve_id = p_curve_id
         and maturity = p_maturity
         and valid_date = p_valid_date
         and origin = 'published'
         and known_from <= p_as_of
       order by known_from;
    return l_versions;
  end get_value_versions;

  function get_changes(
    p_curve_id in varchar2,
    p_from     in date,
    p_to       in date,
    p_since    in timestamp,
    p_as_of    in timestamp
  ) return sys_refcursor is
    l_changes sys_refcursor;
  begin
    open l_changes for
      with old_v as (
        select maturity, valid_date, version_id, value from observation
         where curve_id = p_curve_id and origin = 'published' and valid_date between p_from and p_to
           and known_from <= p_since and p_since < known_to),
      new_v as (
        select maturity, valid_date, version_id, value, change_reason, source_id, known_from from observation
         where curve_id = p_curve_id and origin = 'published' and valid_date between p_from and p_to
           and known_from <= p_as_of and p_as_of < known_to)
      select n.valid_date, n.maturity, o.value old_value, n.value new_value,
             n.change_reason, n.source_id, n.known_from
        from new_v n
        join curve c on c.curve_id = p_curve_id
        join grid_maturity g on g.grid_version = c.grid_version and g.maturity = n.maturity
        left join old_v o on o.maturity = n.maturity and o.valid_date = n.valid_date
       where o.version_id is null or o.version_id <> n.version_id
       order by n.valid_date, g.months;
    return l_changes;
  end get_changes;

  function has_maturity(
    p_curve_id in varchar2,
    p_maturity in varchar2
  ) return number is
    l_count pls_integer;
  begin
    select count(*)
      into l_count
      from curve c
      join grid_maturity g on g.grid_version = c.grid_version
     where c.curve_id = p_curve_id
       and g.maturity = p_maturity;
    return case when l_count > 0 then 1 else 0 end;
  end has_maturity;

  function has_curve(
    p_curve_id in varchar2
  ) return number is
    l_count pls_integer;
  begin
    select count(*)
      into l_count
      from curve
     where curve_id = p_curve_id;
    return case when l_count > 0 then 1 else 0 end;
  end has_curve;

  function latest_valid_date(
    p_curve_id in varchar2,
    p_as_of    in timestamp
  ) return date is
    l_valid_date date;
  begin
    select max(valid_date)
      into l_valid_date
      from observation
     where curve_id = p_curve_id
       and origin = 'published'
       and known_from <= p_as_of
       and p_as_of < known_to;
    return l_valid_date;
  end latest_valid_date;

  function current_knowledge_time return timestamp is
  begin
    return sys_extract_utc(systimestamp);
  end current_knowledge_time;

  function knowledge_horizon return timestamp is
    l_horizon timestamp(6);
  begin
    select known_until
      into l_horizon
      from knowledge_clock
     where clock_id = 1;
    return l_horizon;
  end knowledge_horizon;

end core_observation;
/
