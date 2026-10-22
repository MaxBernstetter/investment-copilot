create or replace package body ut_core_observation as

  c_curve      constant varchar2(64) := 'ut-curve';
  c_other      constant varchar2(64) := 'ut-other-curve';
  c_simulated  constant varchar2(64) := 'ut-simulated-curve';
  c_known_from constant timestamp := timestamp '2026-03-12 18:00:00';
  c_revised_at constant timestamp := timestamp '2026-03-13 18:00:00';
  c_later      constant timestamp := timestamp '2026-03-14 18:00:00';

  type observation_rows is table of observation%rowtype;

  type point_t is record (maturity varchar2(16), months number, value number, version_id number);
  type point_rows is table of point_t;

  type series_point_t is record (valid_date date, value number, version_id number);
  type series_point_rows is table of series_point_t;

  type value_version_t is record (
    version_id            number,
    value                 number,
    known_from            timestamp,
    known_to              timestamp,
    source_id             varchar2(64 char),
    run_id                varchar2(128 char),
    change_reason         varchar2(16 char),
    normalization_version varchar2(64 char),
    delivery_id           varchar2(64 char)
  );
  type value_version_rows is table of value_version_t;

  type change_t is record (
    valid_date    date,
    maturity      varchar2(16 char),
    old_value     number,
    new_value     number,
    change_reason varchar2(16 char),
    source_id     varchar2(64 char),
    known_from    timestamp
  );
  type change_rows is table of change_t;

  c_all_null constant varchar2(4000) := '3M=null,6M=null,1Y=null,2Y=null,3Y=null,5Y=null,'
    || '7Y=null,10Y=null,15Y=null,20Y=null,30Y=null';

  -- A row of core_observation.get_curves.
  type catalogue_row_t is record (
    curve_id     varchar2(64 char),
    label        varchar2(128 char),
    source_id    varchar2(64 char),
    area         varchar2(64 char),
    attribution  varchar2(256 char),
    rate_type    varchar2(16 char),
    compounding  varchar2(16 char),
    unit         varchar2(16 char),
    source_model varchar2(64 char),
    simulated    varchar2(1 char),
    maturity     varchar2(16 char),
    months       number
  );
  type catalogue_rows is table of catalogue_row_t;

  -- All rows of the curve catalogue, as returned by get_curves.
  function catalogue return catalogue_rows is
    l_cursor sys_refcursor := core_observation.get_curves;
    l_rows   catalogue_rows;
  begin
    fetch l_cursor bulk collect into l_rows;
    close l_cursor;
    return l_rows;
  end catalogue;

  -- The test curves live on grid version 1, and the knowledge clock starts at
  -- 1970 so that tests can pass the fixed knowledge times above. utPLSQL rolls
  -- both back after the suite, and each test's own writes are rolled back.
  procedure define_test_curves is
  begin
    update knowledge_clock set known_until = timestamp '1970-01-01 00:00:00' where clock_id = 1;
    insert into curve (curve_id, grid_version, rate_type, compounding, unit,
                       label, source_id, area, attribution)
    values (c_curve, 1, 'spot', 'continuous', 'percent',
            'UT curve', 'ecb', 'Test area', 'Test attribution');
    insert into curve (curve_id, grid_version, rate_type, compounding, unit,
                       label, source_id, area, attribution)
    values (c_other, 1, 'spot', 'continuous', 'percent',
            'UT other curve', 'ecb', 'Test area', 'Test attribution');
    insert into curve (curve_id, grid_version, rate_type, compounding, unit, simulated,
                       label, source_id, area, attribution)
    values (c_simulated, 1, 'spot', 'continuous', 'percent', 'Y',
            'UT simulated curve', 'scenario', 'Test area', 'Test simulated attribution');
  end define_test_curves;

  function version(
    p_maturity       in varchar2 default '10Y',
    p_valid_date     in date     default date '2026-03-12',
    p_value          in number   default 2.61,
    p_curve_id       in varchar2 default c_curve,
    p_origin         in varchar2 default 'published',
    p_method_version in varchar2 default null,
    p_source_id      in varchar2 default 'ecb',
    p_run_id         in varchar2 default 'run-1',
    p_change_reason  in varchar2 default 'initial',
    p_normalization_version in varchar2 default '1',
    p_delivery_id    in varchar2 default 'delivery-1'
  ) return observation_version_t is
  begin
    return observation_version_t(
      p_curve_id, p_maturity, p_valid_date, p_value, p_origin, p_method_version,
      case when p_origin = 'published' then p_source_id end, p_run_id, p_change_reason,
      case when p_origin = 'published' then p_normalization_version end,
      case when p_origin = 'published' then p_delivery_id end
    );
  end version;

  procedure record(
    p_versions   in observation_version_list_t,
    p_known_from in timestamp default c_known_from
  ) is
    l_known_from timestamp;
    l_count      pls_integer;
  begin
    core_observation.record_versions(p_versions, l_known_from, l_count, p_known_from);
  end record;

  -- Records the batch and returns the number of new versions.
  function recorded_count(
    p_versions   in observation_version_list_t,
    p_known_from in timestamp
  ) return pls_integer is
    l_known_from timestamp;
    l_count      pls_integer;
  begin
    core_observation.record_versions(p_versions, l_known_from, l_count, p_known_from);
    return l_count;
  end recorded_count;

  -- Values of the curve's versions visible at knowledge time p_as_of.
  function values_as_of(p_as_of in timestamp) return varchar2 is
    l_values varchar2(4000);
  begin
    select listagg(maturity || '=' || to_char(value, 'TM9'), ',')
             within group (order by maturity)
      into l_values
      from observation
     where curve_id = c_curve
       and known_from <= p_as_of
       and p_as_of < known_to;
    return l_values;
  end values_as_of;

  -- The grid points of the curve as of p_as_of, as maturity=value pairs in
  -- grid order; null when the curve is undefined.
  function points_as_of(
    p_valid_date in date,
    p_as_of      in timestamp,
    p_curve_id   in varchar2 default c_curve
  ) return varchar2 is
    l_cursor sys_refcursor := core_observation.get_as_of(p_curve_id, p_valid_date, p_as_of);
    l_points point_rows;
    l_text   varchar2(4000);
  begin
    fetch l_cursor bulk collect into l_points;
    close l_cursor;
    for i in 1 .. l_points.count loop
      l_text := l_text || case when i > 1 then ',' end || l_points(i).maturity || '='
        || case when l_points(i).value is null then 'null' else to_char(l_points(i).value, 'TM9') end;
    end loop;
    return l_text;
  end points_as_of;

  -- The series of the maturity on the test curve as of p_as_of: date=value
  -- pairs in valid-date order; null when no date has a visible value.
  function series_as_of(
    p_from     in date,
    p_to       in date,
    p_as_of    in timestamp,
    p_maturity in varchar2 default '10Y'
  ) return varchar2 is
    l_cursor sys_refcursor := core_observation.get_series(c_curve, p_maturity, p_from, p_to, p_as_of);
    l_points series_point_rows;
    l_text   varchar2(4000);
  begin
    fetch l_cursor bulk collect into l_points;
    close l_cursor;
    for i in 1 .. l_points.count loop
      l_text := l_text || case when i > 1 then ',' end
        || to_char(l_points(i).valid_date, 'YYYY-MM-DD') || '=' || to_char(l_points(i).value, 'TM9');
    end loop;
    return l_text;
  end series_as_of;

  function stored(p_curve_id in varchar2 default c_curve) return observation_rows is
    l_cursor sys_refcursor := core_observation.get_versions(
      p_curve_id, date '1990-01-01', date '2100-12-31'
    );
    l_rows observation_rows;
  begin
    fetch l_cursor bulk collect into l_rows;
    close l_cursor;
    return l_rows;
  end stored;

  procedure records_valid_and_knowledge_time is
    l_known_from timestamp;
    l_count      pls_integer;
    l_rows       observation_rows;
  begin
    core_observation.record_versions(
      observation_version_list_t(version('2Y', p_value => 2.10), version('10Y')),
      l_known_from, l_count, c_known_from
    );

    l_rows := stored();
    ut.expect(l_count).to_equal(2);
    ut.expect(l_known_from).to_equal(c_known_from);
    ut.expect(l_rows.count).to_equal(2);
    ut.expect(l_rows(1).valid_date).to_equal(date '2026-03-12');
    ut.expect(l_rows(1).maturity).to_equal('10Y');
    ut.expect(l_rows(1).value).to_equal(2.61);
    ut.expect(l_rows(1).known_from).to_equal(c_known_from);
    ut.expect(l_rows(2).maturity).to_equal('2Y');
    ut.expect(l_rows(2).value).to_equal(2.10);
    ut.expect(l_rows(2).known_from).to_equal(c_known_from);
  end records_valid_and_knowledge_time;

  procedure defaults_knowledge_time_to_database_clock is
    l_before     timestamp := sys_extract_utc(systimestamp);
    l_after      timestamp;
    l_known_from timestamp;
    l_count      pls_integer;
  begin
    core_observation.record_versions(
      observation_version_list_t(version()), l_known_from, l_count
    );
    l_after := sys_extract_utc(systimestamp);

    ut.expect(l_known_from).to_be_between(l_before, l_after);
    ut.expect(stored()(1).known_from).to_equal(l_known_from);
  end defaults_knowledge_time_to_database_clock;

  procedure records_open_versions is
  begin
    record(observation_version_list_t(version()));

    ut.expect(stored()(1).known_to).to_equal(core_observation.open_known_to);
  end records_open_versions;

  procedure keeps_provenance is
    l_row observation%rowtype;
  begin
    record(observation_version_list_t(version()));

    l_row := stored()(1);
    ut.expect(l_row.origin).to_equal('published');
    ut.expect(l_row.method_version).to_be_null();
    ut.expect(l_row.source_id).to_equal('ecb');
    ut.expect(l_row.run_id).to_equal('run-1');
    ut.expect(l_row.change_reason).to_equal('initial');
    ut.expect(l_row.normalization_version).to_equal('1');
    ut.expect(l_row.delivery_id).to_equal('delivery-1');
  end keeps_provenance;

  procedure versions_a_changed_value is
    l_rows observation_rows;
  begin
    record(observation_version_list_t(version(p_value => 2.61)));

    ut.expect(
      recorded_count(
        observation_version_list_t(version(p_value => 2.70, p_change_reason => 'revision')),
        c_revised_at
      )
    ).to_equal(1);

    l_rows := stored();
    ut.expect(l_rows.count).to_equal(2);
    ut.expect(l_rows(1).value).to_equal(2.61);
    ut.expect(l_rows(1).known_from).to_equal(c_known_from);
    ut.expect(l_rows(1).known_to).to_equal(c_revised_at);
    ut.expect(l_rows(2).value).to_equal(2.70);
    ut.expect(l_rows(2).known_from).to_equal(c_revised_at);
    ut.expect(l_rows(2).known_to).to_equal(core_observation.open_known_to);
    ut.expect(l_rows(2).change_reason).to_equal('revision');
  end versions_a_changed_value;

  procedure versions_a_changed_source is
    l_rows observation_rows;
  begin
    record(observation_version_list_t(version()));

    ut.expect(
      recorded_count(observation_version_list_t(version(p_source_id => 'bundesbank')), c_revised_at)
    ).to_equal(1);

    l_rows := stored();
    ut.expect(l_rows.count).to_equal(2);
    ut.expect(l_rows(1).source_id).to_equal('ecb');
    ut.expect(l_rows(1).known_to).to_equal(c_revised_at);
    ut.expect(l_rows(2).source_id).to_equal('bundesbank');
    ut.expect(l_rows(2).known_to).to_equal(core_observation.open_known_to);
  end versions_a_changed_source;

  procedure keeps_previous_versions is
    l_rows observation_rows;
  begin
    record(observation_version_list_t(version(p_value => 2.61)));
    record(observation_version_list_t(version(p_value => 2.70)), c_revised_at);
    record(observation_version_list_t(version(p_value => 2.65)), c_later);

    l_rows := stored();
    ut.expect(l_rows.count).to_equal(3);
    ut.expect(l_rows(1).value).to_equal(2.61);
    ut.expect(l_rows(2).value).to_equal(2.70);
    ut.expect(l_rows(3).value).to_equal(2.65);
    ut.expect(l_rows(1).known_to).to_equal(l_rows(2).known_from);
    ut.expect(l_rows(2).known_to).to_equal(l_rows(3).known_from);
    ut.expect(l_rows(3).known_to).to_equal(core_observation.open_known_to);
  end keeps_previous_versions;

  procedure the_first_version_keeps_initial is
  begin
    record(observation_version_list_t(version()));

    ut.expect(stored()(1).change_reason).to_equal('initial');
  end the_first_version_keeps_initial;

  procedure a_later_version_sent_as_initial_is_a_revision is
    l_rows observation_rows;
  begin
    record(observation_version_list_t(version(p_value => 2.61)));

    ut.expect(
      recorded_count(observation_version_list_t(version(p_value => 2.70)), c_revised_at)
    ).to_equal(1);

    l_rows := stored();
    ut.expect(l_rows.count).to_equal(2);
    ut.expect(l_rows(1).change_reason).to_equal('initial');
    ut.expect(l_rows(2).change_reason).to_equal('revision');
  end a_later_version_sent_as_initial_is_a_revision;

  procedure a_later_correction_keeps_its_reason is
    l_rows observation_rows;
  begin
    record(observation_version_list_t(version(p_value => 2.61)));

    ut.expect(
      recorded_count(
        observation_version_list_t(version(p_value => 2.70, p_change_reason => 'correction')),
        c_revised_at
      )
    ).to_equal(1);

    l_rows := stored();
    ut.expect(l_rows.count).to_equal(2);
    ut.expect(l_rows(2).change_reason).to_equal('correction');
  end a_later_correction_keeps_its_reason;

  procedure versions_are_visible_as_of_their_knowledge_time is
  begin
    record(observation_version_list_t(version('2Y', p_value => 2.10), version('10Y', p_value => 2.61)));
    record(
      observation_version_list_t(version('2Y', p_value => 2.10), version('10Y', p_value => 2.70)),
      c_revised_at
    );

    ut.expect(values_as_of(c_known_from - interval '1' second)).to_be_null();
    ut.expect(values_as_of(c_known_from)).to_equal('10Y=2.61,2Y=2.1');
    ut.expect(values_as_of(c_revised_at - interval '1' second)).to_equal('10Y=2.61,2Y=2.1');
    ut.expect(values_as_of(c_revised_at)).to_equal('10Y=2.7,2Y=2.1');
    ut.expect(values_as_of(c_later)).to_equal('10Y=2.7,2Y=2.1');
  end versions_are_visible_as_of_their_knowledge_time;

  procedure unchanged_reload_is_a_no_op is
    l_rows observation_rows;
  begin
    record(observation_version_list_t(version(p_value => 2.61)));

    ut.expect(
      recorded_count(
        observation_version_list_t(
          version(p_value => 2.610, p_run_id => 'run-2', p_change_reason => 'revision')
        ),
        c_revised_at
      )
    ).to_equal(0);

    l_rows := stored();
    ut.expect(l_rows.count).to_equal(1);
    ut.expect(l_rows(1).known_from).to_equal(c_known_from);
    ut.expect(l_rows(1).known_to).to_equal(core_observation.open_known_to);
    ut.expect(l_rows(1).run_id).to_equal('run-1');
    ut.expect(l_rows(1).change_reason).to_equal('initial');
  end unchanged_reload_is_a_no_op;

  procedure a_changed_normalization_version_alone_is_unchanged is
    l_rows observation_rows;
  begin
    record(observation_version_list_t(version(p_normalization_version => '1')));

    ut.expect(
      recorded_count(
        observation_version_list_t(version(p_normalization_version => '2')), c_revised_at
      )
    ).to_equal(0);

    l_rows := stored();
    ut.expect(l_rows.count).to_equal(1);
    ut.expect(l_rows(1).normalization_version).to_equal('1');
    ut.expect(l_rows(1).known_to).to_equal(core_observation.open_known_to);
  end a_changed_normalization_version_alone_is_unchanged;

  procedure a_new_delivery_alone_is_unchanged is
    l_rows observation_rows;
  begin
    record(observation_version_list_t(version(p_delivery_id => 'delivery-1')));

    ut.expect(
      recorded_count(
        observation_version_list_t(version(p_delivery_id => 'delivery-2')), c_revised_at
      )
    ).to_equal(0);

    l_rows := stored();
    ut.expect(l_rows.count).to_equal(1);
    ut.expect(l_rows(1).delivery_id).to_equal('delivery-1');
    ut.expect(l_rows(1).known_to).to_equal(core_observation.open_known_to);
  end a_new_delivery_alone_is_unchanged;

  procedure records_a_mixed_batch is
    l_rows observation_rows;
  begin
    record(observation_version_list_t(version('2Y', p_value => 2.10), version('10Y', p_value => 2.61)));

    ut.expect(
      recorded_count(
        observation_version_list_t(
          version('2Y', p_value => 2.10),
          version('10Y', p_value => 2.70),
          version('30Y', p_value => 2.95)
        ),
        c_revised_at
      )
    ).to_equal(2);

    -- ordered by maturity, then known_from: 10Y (old, new), 2Y, 30Y
    l_rows := stored();
    ut.expect(l_rows.count).to_equal(4);
    ut.expect(l_rows(1).maturity || ' ' || l_rows(1).value).to_equal('10Y 2.61');
    ut.expect(l_rows(1).known_to).to_equal(c_revised_at);
    ut.expect(l_rows(2).maturity || ' ' || l_rows(2).value).to_equal('10Y 2.7');
    ut.expect(l_rows(2).known_from).to_equal(c_revised_at);
    ut.expect(l_rows(3).maturity).to_equal('2Y');
    ut.expect(l_rows(3).known_from).to_equal(c_known_from);
    ut.expect(l_rows(3).known_to).to_equal(core_observation.open_known_to);
    ut.expect(l_rows(4).maturity).to_equal('30Y');
    ut.expect(l_rows(4).known_from).to_equal(c_revised_at);
  end records_a_mixed_batch;

  procedure versions_origins_and_method_versions_independently is
    l_rows observation_rows;
  begin
    record(observation_version_list_t(
      version(p_value => 2.61),
      version(p_value => 2.58, p_origin => 'derived', p_method_version => 'nss-1'),
      version(p_value => 2.59, p_origin => 'derived', p_method_version => 'nss-2')
    ));

    ut.expect(
      recorded_count(
        observation_version_list_t(
          version(p_value => 2.61),
          version(p_value => 2.60, p_origin => 'derived', p_method_version => 'nss-1'),
          version(p_value => 2.59, p_origin => 'derived', p_method_version => 'nss-2')
        ),
        c_revised_at
      )
    ).to_equal(1);

    -- ordered by origin, method_version, known_from: nss-1 (old, new), nss-2, published
    l_rows := stored();
    ut.expect(l_rows.count).to_equal(4);
    ut.expect(l_rows(1).method_version || ' ' || l_rows(1).value).to_equal('nss-1 2.58');
    ut.expect(l_rows(1).known_to).to_equal(c_revised_at);
    ut.expect(l_rows(2).method_version || ' ' || l_rows(2).value).to_equal('nss-1 2.6');
    ut.expect(l_rows(3).method_version).to_equal('nss-2');
    ut.expect(l_rows(3).known_to).to_equal(core_observation.open_known_to);
    ut.expect(l_rows(4).origin).to_equal('published');
    ut.expect(l_rows(4).known_to).to_equal(core_observation.open_known_to);
  end versions_origins_and_method_versions_independently;

  procedure rejects_duplicates_in_batch is
    l_rows observation_rows;
  begin
    record(observation_version_list_t(version('10Y', p_value => 2.61)));

    begin
      record(
        observation_version_list_t(
          version('2Y'), version('10Y', p_value => 2.70), version('10Y', p_value => 2.80)
        ),
        c_revised_at
      );
      ut.fail('expected ORA-20002');
    exception
      when others then
        ut.expect(sqlcode).to_equal(core_observation.duplicate_observation);
    end;

    l_rows := stored();
    ut.expect(l_rows.count).to_equal(1);
    ut.expect(l_rows(1).value).to_equal(2.61);
    ut.expect(l_rows(1).known_to).to_equal(core_observation.open_known_to);
  end rejects_duplicates_in_batch;

  procedure rejects_an_undefined_curve is
  begin
    begin
      record(observation_version_list_t(
        version('10Y'), version('10Y', p_curve_id => 'ut-undefined-curve')
      ));
      ut.fail('expected ORA-20003');
    exception
      when others then
        ut.expect(sqlcode).to_equal(core_observation.off_grid_observation);
    end;

    ut.expect(stored().count).to_equal(0);
  end rejects_an_undefined_curve;

  procedure rejects_a_maturity_off_the_grid is
  begin
    begin
      record(observation_version_list_t(version('10Y'), version('4Y')));
      ut.fail('expected ORA-20003');
    exception
      when others then
        ut.expect(sqlcode).to_equal(core_observation.off_grid_observation);
    end;

    ut.expect(stored().count).to_equal(0);
  end rejects_a_maturity_off_the_grid;

  procedure records_scenario_values_on_a_simulated_curve is
    l_count pls_integer;
  begin
    l_count := recorded_count(
      observation_version_list_t(version(p_curve_id => c_simulated, p_source_id => 'scenario')),
      c_known_from
    );

    ut.expect(l_count).to_equal(1);
    ut.expect(stored(c_simulated).count).to_equal(1);
  end records_scenario_values_on_a_simulated_curve;

  procedure rejects_a_scenario_value_on_a_real_curve is
  begin
    begin
      record(observation_version_list_t(version(p_source_id => 'scenario')));
      ut.fail('expected ORA-20005');
    exception
      when others then
        ut.expect(sqlcode).to_equal(core_observation.simulated_mismatch);
    end;

    ut.expect(stored().count).to_equal(0);
  end rejects_a_scenario_value_on_a_real_curve;

  procedure rejects_a_source_value_on_a_simulated_curve is
  begin
    begin
      record(observation_version_list_t(
        version(p_curve_id => c_simulated), version('3Y', p_curve_id => c_simulated)
      ));
      ut.fail('expected ORA-20005');
    exception
      when others then
        ut.expect(sqlcode).to_equal(core_observation.simulated_mismatch);
    end;

    ut.expect(stored(c_simulated).count).to_equal(0);
  end rejects_a_source_value_on_a_simulated_curve;

  procedure records_nothing_for_empty_batch is
    l_known_from timestamp;
    l_count      pls_integer;
  begin
    core_observation.record_versions(
      observation_version_list_t(), l_known_from, l_count, c_known_from
    );

    ut.expect(l_count).to_equal(0);
    ut.expect(stored().count).to_equal(0);
  end records_nothing_for_empty_batch;

  procedure requires_method_version_for_derived is
  begin
    record(observation_version_list_t(version(p_origin => 'derived')));
  end requires_method_version_for_derived;

  procedure gets_versions_of_curve_and_range is
    l_cursor sys_refcursor;
    l_rows   observation_rows;
  begin
    record(observation_version_list_t(
      version(p_valid_date => date '2026-03-11'),
      version(p_valid_date => date '2026-03-12'),
      version(p_valid_date => date '2026-04-01'),
      version(p_valid_date => date '2026-03-12', p_curve_id => c_other)
    ));

    l_cursor := core_observation.get_versions(c_curve, date '2026-03-12', date '2026-04-01');
    fetch l_cursor bulk collect into l_rows;
    close l_cursor;

    ut.expect(l_rows.count).to_equal(2);
    ut.expect(l_rows(1).valid_date).to_equal(date '2026-03-12');
    ut.expect(l_rows(2).valid_date).to_equal(date '2026-04-01');
    ut.expect(l_rows(1).curve_id).to_equal(c_curve);
  end gets_versions_of_curve_and_range;

  procedure as_of_returns_the_grid_in_order is
  begin
    record(observation_version_list_t(
      version('2Y', p_valid_date => date '2026-04-01', p_value => 2.10),
      version('10Y', p_valid_date => date '2026-04-01', p_value => 2.61)
    ));

    ut.expect(points_as_of(date '2026-04-01', c_known_from)).to_equal(
      '3M=null,6M=null,1Y=null,2Y=2.1,3Y=null,5Y=null,7Y=null,10Y=2.61,15Y=null,20Y=null,30Y=null'
    );
  end as_of_returns_the_grid_in_order;

  procedure as_of_returns_the_version_known_then is
  begin
    record(observation_version_list_t(
      version('10Y', p_valid_date => date '2026-04-01', p_value => 2.61)
    ));
    record(observation_version_list_t(
      version('10Y', p_valid_date => date '2026-04-01', p_value => 2.70, p_change_reason => 'revision')
    ), c_revised_at);

    ut.expect(points_as_of(date '2026-04-01', c_known_from)).to_be_like('%10Y=2.61,%');
    ut.expect(points_as_of(date '2026-04-01', c_revised_at - interval '1' second))
      .to_be_like('%10Y=2.61,%');
    ut.expect(points_as_of(date '2026-04-01', c_revised_at)).to_be_like('%10Y=2.7,%');
    ut.expect(points_as_of(date '2026-04-01', c_later)).to_be_like('%10Y=2.7,%');
  end as_of_returns_the_version_known_then;

  procedure as_of_before_first_knowledge_is_empty is
  begin
    record(observation_version_list_t(
      version('10Y', p_valid_date => date '2026-04-01', p_value => 2.61)
    ));

    ut.expect(points_as_of(date '2026-04-01', c_known_from - interval '1' second))
      .to_equal(c_all_null);
  end as_of_before_first_knowledge_is_empty;

  procedure as_of_ignores_derived_values is
  begin
    record(observation_version_list_t(
      version('10Y', p_valid_date => date '2026-04-01', p_origin => 'derived',
              p_method_version => 'm1', p_value => 2.50)
    ));

    ut.expect(points_as_of(date '2026-04-01', c_later)).to_equal(c_all_null);
  end as_of_ignores_derived_values;

  procedure as_of_of_an_undefined_curve_has_no_rows is
  begin
    ut.expect(points_as_of(date '2026-04-01', c_known_from, p_curve_id => 'ut-undefined')).to_be_null();
  end as_of_of_an_undefined_curve_has_no_rows;

  procedure latest_valid_date_as_of is
  begin
    record(observation_version_list_t(
      version(p_valid_date => date '2026-04-01', p_value => 2.61)
    ), c_known_from);
    record(observation_version_list_t(
      version(p_valid_date => date '2026-04-02', p_value => 2.70)
    ), c_revised_at);

    ut.expect(core_observation.latest_valid_date(c_curve, c_known_from - interval '1' second))
      .to_be_null();
    ut.expect(core_observation.latest_valid_date(c_curve, c_known_from))
      .to_equal(date '2026-04-01');
    ut.expect(core_observation.latest_valid_date(c_curve, c_revised_at))
      .to_equal(date '2026-04-02');
  end latest_valid_date_as_of;

  procedure series_returns_known_dates_in_order is
  begin
    record(observation_version_list_t(
      version(p_valid_date => date '2026-04-03', p_value => 2.80),
      version(p_valid_date => date '2026-04-01', p_value => 2.61),
      version(p_valid_date => date '2026-04-02', p_value => 2.70),
      version(p_valid_date => date '2026-04-02', p_maturity => '2Y', p_value => 2.10)
    ));

    ut.expect(series_as_of(date '2026-04-01', date '2026-04-03', c_known_from))
      .to_equal('2026-04-01=2.61,2026-04-02=2.7,2026-04-03=2.8');
    ut.expect(series_as_of(date '2026-04-02', date '2026-04-02', c_known_from))
      .to_equal('2026-04-02=2.7');
  end series_returns_known_dates_in_order;

  procedure series_returns_the_version_known_then is
  begin
    record(observation_version_list_t(
      version(p_valid_date => date '2026-04-01', p_value => 2.61)
    ));
    record(observation_version_list_t(
      version(p_valid_date => date '2026-04-01', p_value => 2.70, p_change_reason => 'revision')
    ), c_revised_at);

    ut.expect(series_as_of(date '2026-04-01', date '2026-04-01', c_known_from))
      .to_equal('2026-04-01=2.61');
    ut.expect(series_as_of(date '2026-04-01', date '2026-04-01', c_revised_at - interval '1' second))
      .to_equal('2026-04-01=2.61');
    ut.expect(series_as_of(date '2026-04-01', date '2026-04-01', c_revised_at))
      .to_equal('2026-04-01=2.7');
    ut.expect(series_as_of(date '2026-04-01', date '2026-04-01', c_later))
      .to_equal('2026-04-01=2.7');
  end series_returns_the_version_known_then;

  procedure series_omits_dates_without_a_visible_version is
  begin
    record(observation_version_list_t(
      version(p_valid_date => date '2026-04-01', p_value => 2.61),
      version(p_valid_date => date '2026-04-03', p_value => 2.80)
    ));
    record(observation_version_list_t(
      version(p_valid_date => date '2026-04-02', p_value => 2.70)
    ), c_revised_at);

    ut.expect(series_as_of(date '2026-04-01', date '2026-04-03', c_known_from))
      .to_equal('2026-04-01=2.61,2026-04-03=2.8');
    ut.expect(series_as_of(date '2026-04-01', date '2026-04-03', c_revised_at))
      .to_equal('2026-04-01=2.61,2026-04-02=2.7,2026-04-03=2.8');
    ut.expect(series_as_of(date '2026-04-01', date '2026-04-03', c_known_from - interval '1' second))
      .to_be_null();
  end series_omits_dates_without_a_visible_version;

  procedure has_maturity_checks_the_grid is
  begin
    ut.expect(core_observation.has_maturity(c_curve, '10Y')).to_equal(1);
    ut.expect(core_observation.has_maturity(c_curve, '4Y')).to_equal(0);
    ut.expect(core_observation.has_maturity('ut-undefined', '10Y')).to_equal(0);
  end has_maturity_checks_the_grid;

  -- The versions of the 10Y value of 2026-03-12 on the test curve, as known at p_as_of.
  function value_versions(
    p_as_of      in timestamp,
    p_maturity   in varchar2 default '10Y',
    p_curve_id   in varchar2 default c_curve
  ) return value_version_rows is
    l_cursor sys_refcursor := core_observation.get_value_versions(
      p_curve_id, p_maturity, date '2026-03-12', p_as_of
    );
    l_rows value_version_rows;
  begin
    fetch l_cursor bulk collect into l_rows;
    close l_cursor;
    return l_rows;
  end value_versions;

  procedure value_versions_lists_versions_known_then_oldest_first is
    l_rows value_version_rows;
  begin
    record(observation_version_list_t(version(p_value => 2.61)));
    record(observation_version_list_t(version(p_value => 2.70, p_change_reason => 'revision')), c_revised_at);
    record(observation_version_list_t(version(p_value => 2.65, p_change_reason => 'correction')), c_later);

    l_rows := value_versions(c_later);

    ut.expect(l_rows.count).to_equal(3);
    ut.expect(l_rows(1).value).to_equal(2.61);
    ut.expect(l_rows(1).known_from).to_equal(c_known_from);
    ut.expect(l_rows(1).known_to).to_equal(c_revised_at);
    ut.expect(l_rows(2).value).to_equal(2.70);
    ut.expect(l_rows(2).known_from).to_equal(c_revised_at);
    ut.expect(l_rows(2).change_reason).to_equal('revision');
    ut.expect(l_rows(3).value).to_equal(2.65);
    ut.expect(l_rows(3).change_reason).to_equal('correction');
    ut.expect(l_rows(3).known_to).to_be_null();
  end value_versions_lists_versions_known_then_oldest_first;

  procedure value_versions_hide_later_knowledge is
    l_rows value_version_rows;
  begin
    record(observation_version_list_t(version(p_value => 2.61)));
    record(observation_version_list_t(version(p_value => 2.70, p_change_reason => 'revision')), c_revised_at);
    record(observation_version_list_t(version(p_value => 2.65, p_change_reason => 'correction')), c_later);

    -- Before the revision: only the first version, still current, so known_to is null.
    l_rows := value_versions(c_revised_at - interval '1' second);
    ut.expect(l_rows.count).to_equal(1);
    ut.expect(l_rows(1).value).to_equal(2.61);
    ut.expect(l_rows(1).known_to).to_be_null();

    -- At the revision: the first version is closed at as_of and is shown with it.
    l_rows := value_versions(c_revised_at);
    ut.expect(l_rows.count).to_equal(2);
    ut.expect(l_rows(1).known_to).to_equal(c_revised_at);
    ut.expect(l_rows(2).value).to_equal(2.70);
    ut.expect(l_rows(2).known_to).to_be_null();

    -- Before the first knowledge time: nothing is known.
    l_rows := value_versions(c_known_from - interval '1' second);
    ut.expect(l_rows.count).to_equal(0);
  end value_versions_hide_later_knowledge;

  procedure value_versions_ignore_derived_values is
    l_rows value_version_rows;
  begin
    record(observation_version_list_t(
      version('10Y', p_value => 2.50, p_origin => 'derived', p_method_version => 'm1')
    ));
    l_rows := value_versions(c_later);
    ut.expect(l_rows.count).to_equal(0);

    -- Knowledge time increases strictly (knowledge clock), so the second call is later.
    record(observation_version_list_t(version('10Y', p_value => 2.61)), c_revised_at);
    l_rows := value_versions(c_later);
    ut.expect(l_rows.count).to_equal(1);
    ut.expect(l_rows(1).value).to_equal(2.61);
  end value_versions_ignore_derived_values;

  procedure value_versions_of_an_unknown_value_are_empty is
    l_rows value_version_rows;
  begin
    l_rows := value_versions(c_later);
    ut.expect(l_rows.count).to_equal(0);

    record(observation_version_list_t(version('2Y', p_value => 2.10)));
    l_rows := value_versions(c_later, p_maturity => '10Y');
    ut.expect(l_rows.count).to_equal(0);
    l_rows := value_versions(c_later, p_maturity => '2Y');
    ut.expect(l_rows.count).to_equal(1);
  end value_versions_of_an_unknown_value_are_empty;

  procedure knowledge_time_is_after_the_horizon is
    l_horizon    timestamp := core_observation.knowledge_horizon();
    l_known_from timestamp;
    l_count      pls_integer;
  begin
    core_observation.record_versions(observation_version_list_t(version()), l_known_from, l_count);

    ut.expect(l_known_from > l_horizon).to_be_true();
  end knowledge_time_is_after_the_horizon;

  procedure a_call_advances_the_horizon is
    l_known_from timestamp;
    l_count      pls_integer;
  begin
    core_observation.record_versions(observation_version_list_t(version()), l_known_from, l_count);

    ut.expect(core_observation.knowledge_horizon()).to_equal(l_known_from);
  end a_call_advances_the_horizon;

  procedure knowledge_time_increases_when_the_clock_lags is
    l_horizon    timestamp;
    l_known_from timestamp;
    l_count      pls_integer;
  begin
    -- The horizon ends up an hour ahead of the database clock.
    update knowledge_clock
       set known_until = sys_extract_utc(systimestamp) + interval '1' hour
     where clock_id = 1;
    l_horizon := core_observation.knowledge_horizon();

    core_observation.record_versions(observation_version_list_t(version()), l_known_from, l_count);

    ut.expect(l_known_from).to_equal(l_horizon + interval '0.000001' second);
  end knowledge_time_increases_when_the_clock_lags;

  procedure rejects_a_given_knowledge_time_not_after_the_horizon is
    l_rows observation_rows;
  begin
    record(observation_version_list_t(version('10Y', p_value => 2.61)), c_later);

    begin
      record(observation_version_list_t(version('10Y', p_value => 2.70)), c_revised_at);
      ut.fail('expected ORA-20004');
    exception
      when others then
        ut.expect(sqlcode).to_equal(core_observation.knowledge_time_not_increasing);
    end;

    ut.expect(core_observation.knowledge_horizon()).to_equal(c_later);
    l_rows := stored();
    ut.expect(l_rows.count).to_equal(1);
    ut.expect(l_rows(1).value).to_equal(2.61);
  end rejects_a_given_knowledge_time_not_after_the_horizon;

  procedure a_failed_call_keeps_the_horizon is
  begin
    record(observation_version_list_t(version()), c_later);

    begin
      record(observation_version_list_t(version('4Y')));
      ut.fail('expected ORA-20003');
    exception
      when others then
        ut.expect(sqlcode).to_equal(core_observation.off_grid_observation);
    end;

    ut.expect(core_observation.knowledge_horizon()).to_equal(c_later);
  end a_failed_call_keeps_the_horizon;


  -- The changes of the test curve between two knowledge times, as
  -- date|maturity|old|new|reason pairs joined by commas; null when there are none.
  function changes_text(
    p_from     in date,
    p_to       in date,
    p_since    in timestamp,
    p_as_of    in timestamp,
    p_curve_id in varchar2 default c_curve
  ) return varchar2 is
    l_cursor  sys_refcursor := core_observation.get_changes(p_curve_id, p_from, p_to, p_since, p_as_of);
    l_changes change_rows;
    l_text    varchar2(4000);
  begin
    fetch l_cursor bulk collect into l_changes;
    close l_cursor;
    for i in 1 .. l_changes.count loop
      l_text := l_text || case when i > 1 then ',' end
        || to_char(l_changes(i).valid_date, 'YYYY-MM-DD') || '|' || l_changes(i).maturity || '|'
        || case when l_changes(i).old_value is null then 'null' else to_char(l_changes(i).old_value, 'TM9') end || '|'
        || to_char(l_changes(i).new_value, 'TM9') || '|' || l_changes(i).change_reason;
    end loop;
    return l_text;
  end changes_text;

  -- The changes rows of the test curve between two knowledge times.
  function changes(
    p_from  in date,
    p_to    in date,
    p_since in timestamp,
    p_as_of in timestamp
  ) return change_rows is
    l_cursor  sys_refcursor := core_observation.get_changes(c_curve, p_from, p_to, p_since, p_as_of);
    l_changes change_rows;
  begin
    fetch l_cursor bulk collect into l_changes;
    close l_cursor;
    return l_changes;
  end changes;

  procedure changes_list_values_whose_version_changed is
    l_changes change_rows;
  begin
    record(observation_version_list_t(version('2Y', p_value => 2.10), version('10Y')), c_known_from);
    record(observation_version_list_t(
      version(p_value => 2.70, p_change_reason => 'correction')
    ), c_revised_at);

    ut.expect(changes_text(date '2026-03-12', date '2026-03-12', c_known_from, c_revised_at))
      .to_equal('2026-03-12|10Y|2.61|2.7|correction');

    l_changes := changes(date '2026-03-12', date '2026-03-12', c_known_from, c_revised_at);
    ut.expect(l_changes.count).to_equal(1);
    ut.expect(l_changes(1).source_id).to_equal('ecb');
    ut.expect(l_changes(1).known_from).to_equal(c_revised_at);
  end changes_list_values_whose_version_changed;

  procedure changes_include_values_first_known_later is
    l_changes change_rows;
  begin
    record(observation_version_list_t(version()), c_known_from);
    record(observation_version_list_t(version('2Y', p_value => 2.10)), c_revised_at);

    ut.expect(changes_text(date '2026-03-12', date '2026-03-12', c_known_from, c_revised_at))
      .to_equal('2026-03-12|2Y|null|2.1|initial');

    l_changes := changes(date '2026-03-12', date '2026-03-12', c_known_from, c_revised_at);
    ut.expect(l_changes(1).old_value).to_be_null();
    ut.expect(l_changes(1).known_from).to_equal(c_revised_at);
  end changes_include_values_first_known_later;

  procedure changes_compare_two_states_not_intermediate_versions is
  begin
    record(observation_version_list_t(version(p_value => 2.61)), c_known_from);
    record(observation_version_list_t(version(p_value => 2.70, p_change_reason => 'revision')), c_revised_at);
    record(observation_version_list_t(version(p_value => 2.65, p_change_reason => 'correction')), c_later);

    ut.expect(changes_text(date '2026-03-12', date '2026-03-12', c_known_from, c_later))
      .to_equal('2026-03-12|10Y|2.61|2.65|correction');
  end changes_compare_two_states_not_intermediate_versions;

  procedure changes_between_equal_times_are_empty is
  begin
    record(observation_version_list_t(version(p_value => 2.61)), c_known_from);
    record(observation_version_list_t(version(p_value => 2.70, p_change_reason => 'correction')), c_revised_at);

    ut.expect(changes_text(date '2026-03-12', date '2026-03-12', c_revised_at, c_revised_at))
      .to_be_null();
  end changes_between_equal_times_are_empty;

  procedure changes_respect_the_valid_date_range is
  begin
    record(observation_version_list_t(
      version(p_value => 2.61),
      version(p_valid_date => date '2026-03-13', p_value => 2.62)
    ), c_known_from);
    record(observation_version_list_t(
      version(p_value => 2.70, p_change_reason => 'correction'),
      version(p_valid_date => date '2026-03-13', p_value => 2.71, p_change_reason => 'correction')
    ), c_revised_at);

    ut.expect(changes_text(date '2026-03-13', date '2026-03-13', c_known_from, c_revised_at))
      .to_equal('2026-03-13|10Y|2.62|2.71|correction');
  end changes_respect_the_valid_date_range;

  procedure changes_ignore_derived_values is
  begin
    record(observation_version_list_t(
      version(p_value => 2.50, p_origin => 'derived', p_method_version => 'm1')
    ), c_known_from);
    record(observation_version_list_t(
      version(p_value => 2.55, p_origin => 'derived', p_method_version => 'm1')
    ), c_revised_at);

    ut.expect(changes_text(date '2026-03-12', date '2026-03-12', c_known_from, c_revised_at))
      .to_be_null();
  end changes_ignore_derived_values;

  procedure has_curve_checks_the_definition is
  begin
    ut.expect(core_observation.has_curve(c_curve)).to_equal(1);
    ut.expect(core_observation.has_curve('ut-undefined')).to_equal(0);
  end has_curve_checks_the_definition;

  procedure curves_list_each_curve_with_its_grid_in_order is
    l_rows catalogue_rows := catalogue;
    l_mine catalogue_rows := catalogue_rows();
  begin
    for i in 1 .. l_rows.count loop
      if l_rows(i).curve_id = c_curve then
        l_mine.extend;
        l_mine(l_mine.count) := l_rows(i);
      end if;
    end loop;

    ut.expect(l_mine.count).to_equal(11);
    ut.expect(l_mine(1).maturity).to_equal('3M');
    ut.expect(l_mine(l_mine.count).maturity).to_equal('30Y');
    ut.expect(l_mine(1).label).to_equal('UT curve');
    ut.expect(l_mine(1).source_id).to_equal('ecb');
    ut.expect(l_mine(1).area).to_equal('Test area');
    ut.expect(l_mine(1).attribution).to_equal('Test attribution');
    ut.expect(l_mine(1).rate_type).to_equal('spot');
    ut.expect(l_mine(1).compounding).to_equal('continuous');
    ut.expect(l_mine(1).unit).to_equal('percent');
    ut.expect(l_mine(1).source_model).to_be_null();
    ut.expect(l_mine(1).simulated).to_equal('N');
  end curves_list_each_curve_with_its_grid_in_order;

  procedure curves_flag_a_simulated_curve is
    l_rows catalogue_rows := catalogue;
    l_count pls_integer := 0;
    l_all_scenario boolean := true;
    l_all_simulated boolean := true;
  begin
    for i in 1 .. l_rows.count loop
      if l_rows(i).curve_id = c_simulated then
        l_count := l_count + 1;
        l_all_simulated := l_all_simulated and l_rows(i).simulated = 'Y';
        l_all_scenario := l_all_scenario and l_rows(i).source_id = 'scenario';
      end if;
    end loop;

    ut.expect(l_count).to_equal(11);
    ut.expect(l_all_simulated).to_be_true();
    ut.expect(l_all_scenario).to_be_true();
  end curves_flag_a_simulated_curve;

  procedure curves_are_ordered_by_curve_and_months is
    l_rows catalogue_rows := catalogue;
    l_ordered boolean := true;
  begin
    for i in 2 .. l_rows.count loop
      l_ordered := l_ordered and (
        l_rows(i - 1).curve_id < l_rows(i).curve_id
        or (l_rows(i - 1).curve_id = l_rows(i).curve_id
            and l_rows(i - 1).months < l_rows(i).months)
      );
    end loop;
    ut.expect(l_ordered).to_be_true();
  end curves_are_ordered_by_curve_and_months;

end ut_core_observation;
/
