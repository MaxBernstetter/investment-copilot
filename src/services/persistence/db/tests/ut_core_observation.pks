create or replace package ut_core_observation as
  -- utPLSQL tests of core_observation. Installed into CORE by the integration
  -- tests only; never part of a migration.

  --%suite(core_observation)
  --%suitepath(core)

  --%test(Records every observation with its valid time and the given knowledge time)
  procedure records_valid_and_knowledge_time;

  --%test(Uses the database clock in UTC when no knowledge time is given)
  procedure defaults_knowledge_time_to_database_clock;

  --%test(Records new versions as open)
  procedure records_open_versions;

  --%test(Keeps the provenance of every version)
  procedure keeps_provenance;

  --%test(Rejects a second open version and records nothing of the batch)
  procedure rejects_second_open_version;

  --%test(Rejects an observation that appears twice in one batch)
  --%throws(core_observation.open_version_exists)
  procedure rejects_duplicates_in_batch;

  --%test(Records nothing for an empty batch)
  procedure records_nothing_for_empty_batch;

  --%test(Requires a method version for derived values)
  --%throws(-2290)
  procedure requires_method_version_for_derived;

  --%test(Returns only the versions of the requested curve and valid-date range)
  procedure gets_versions_of_curve_and_range;
end ut_core_observation;
/
