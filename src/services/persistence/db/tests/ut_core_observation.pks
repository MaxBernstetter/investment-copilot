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

  --%test(A changed value closes the open version and opens a new one)
  procedure versions_a_changed_value;

  --%test(A changed source closes the open version and opens a new one)
  procedure versions_a_changed_source;

  --%test(Keeps every previous version with contiguous knowledge intervals)
  procedure keeps_previous_versions;

  --%test(Each version is visible as of its own knowledge interval)
  procedure versions_are_visible_as_of_their_knowledge_time;

  --%test(An unchanged reload records nothing and keeps the open version as it was)
  procedure unchanged_reload_is_a_no_op;

  --%test(Records new, versions changed and skips unchanged observations in one batch)
  procedure records_a_mixed_batch;

  --%test(Versions observations of different origins and method versions independently)
  procedure versions_origins_and_method_versions_independently;

  --%test(Rejects an observation that appears twice in one batch and stores nothing of it)
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
