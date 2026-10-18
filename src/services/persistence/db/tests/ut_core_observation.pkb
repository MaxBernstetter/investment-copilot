create or replace package body ut_core_observation as

  c_curve      constant varchar2(64) := 'ut-curve';
  c_other      constant varchar2(64) := 'ut-other-curve';
  c_known_from constant timestamp := timestamp '2026-03-12 18:00:00';

  type observation_rows is table of observation%rowtype;

  function version(
    p_maturity       in varchar2 default '10Y',
    p_valid_date     in date     default date '2026-03-12',
    p_value          in number   default 2.61,
    p_curve_id       in varchar2 default c_curve,
    p_origin         in varchar2 default 'published',
    p_method_version in varchar2 default null
  ) return observation_version_t is
  begin
    return observation_version_t(
      p_curve_id, p_maturity, p_valid_date, p_value, p_origin, p_method_version,
      case when p_origin = 'published' then 'ecb' end, 'run-1', 'initial'
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
  end keeps_provenance;

  procedure rejects_second_open_version is
  begin
    record(observation_version_list_t(version('10Y')));

    begin
      record(
        observation_version_list_t(version('2Y'), version('10Y', p_value => 2.70)),
        c_known_from + interval '1' day
      );
      ut.fail('expected ORA-20001');
    exception
      when others then
        ut.expect(sqlcode).to_equal(core_observation.open_version_exists);
    end;

    ut.expect(stored().count).to_equal(1);
  end rejects_second_open_version;

  procedure rejects_duplicates_in_batch is
  begin
    record(observation_version_list_t(version(), version(p_value => 2.70)));
  end rejects_duplicates_in_batch;

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

end ut_core_observation;
/
