create or replace package ut_core_observation as
  -- utPLSQL tests of core_observation. Installed into CORE by the integration
  -- tests only; never part of a migration.

  --%suite(core_observation)
  --%suitepath(core)

  --%beforeall
  procedure define_test_curves;

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

  --%test(The first version keeps its initial change reason)
  procedure the_first_version_keeps_initial;

  --%test(A later version sent as initial is stored as a revision)
  procedure a_later_version_sent_as_initial_is_a_revision;

  --%test(A later correction keeps its change reason)
  procedure a_later_correction_keeps_its_reason;

  --%test(Each version is visible as of its own knowledge interval)
  procedure versions_are_visible_as_of_their_knowledge_time;

  --%test(An unchanged reload records nothing and keeps the open version as it was)
  procedure unchanged_reload_is_a_no_op;

  --%test(A reload that differs only in its normalization version records nothing)
  procedure a_changed_normalization_version_alone_is_unchanged;

  --%test(A reload that differs only in its source delivery records nothing)
  procedure a_new_delivery_alone_is_unchanged;

  --%test(Records new, versions changed and skips unchanged observations in one batch)
  procedure records_a_mixed_batch;

  --%test(Versions observations of different origins and method versions independently)
  procedure versions_origins_and_method_versions_independently;

  --%test(Rejects an observation that appears twice in one batch and stores nothing of it)
  procedure rejects_duplicates_in_batch;

  --%test(Rejects an observation of an undefined curve and stores nothing of the batch)
  procedure rejects_an_undefined_curve;

  --%test(Rejects a maturity off the curve's grid and stores nothing of the batch)
  procedure rejects_a_maturity_off_the_grid;

  --%test(Records scenario values on a simulated curve)
  procedure records_scenario_values_on_a_simulated_curve;

  --%test(Rejects a scenario value on a real curve and stores nothing of the batch)
  procedure rejects_a_scenario_value_on_a_real_curve;

  --%test(Rejects a source value on a simulated curve and stores nothing of the batch)
  procedure rejects_a_source_value_on_a_simulated_curve;

  --%test(Records nothing for an empty batch)
  procedure records_nothing_for_empty_batch;

  --%test(Requires a method version for derived values)
  --%throws(-2290)
  procedure requires_method_version_for_derived;

  --%test(Returns only the versions of the requested curve and valid-date range)
  procedure gets_versions_of_curve_and_range;

  --%test(As-of returns every maturity of the grid in order, with the published values)
  procedure as_of_returns_the_grid_in_order;

  --%test(As-of returns the version that was known at the given time)
  procedure as_of_returns_the_version_known_then;

  --%test(As-of before the first knowledge time has no values)
  procedure as_of_before_first_knowledge_is_empty;

  --%test(As-of ignores derived values)
  procedure as_of_ignores_derived_values;

  --%test(As-of of an undefined curve has no rows)
  procedure as_of_of_an_undefined_curve_has_no_rows;

  --%test(Latest valid date is the latest published valid date known at the given time)
  procedure latest_valid_date_as_of;

  --%test(Series returns the known dates of the maturity in valid-date order)
  procedure series_returns_known_dates_in_order;

  --%test(Series returns the version that was known at the given time)
  procedure series_returns_the_version_known_then;

  --%test(Series omits dates without a visible published version)
  procedure series_omits_dates_without_a_visible_version;

  --%test(Has maturity checks the grid of the curve)
  procedure has_maturity_checks_the_grid;

  --%test(Value versions list the versions known then, oldest first)
  procedure value_versions_lists_versions_known_then_oldest_first;

  --%test(Value versions hide knowledge later than the requested time)
  procedure value_versions_hide_later_knowledge;

  --%test(Value versions ignore derived values)
  procedure value_versions_ignore_derived_values;

  --%test(Value versions of an unknown value are empty)
  procedure value_versions_of_an_unknown_value_are_empty;

  --%test(A knowledge time is after the knowledge horizon before the call)
  procedure knowledge_time_is_after_the_horizon;

  --%test(A call advances the knowledge horizon to its knowledge time)
  procedure a_call_advances_the_horizon;

  --%test(Knowledge time moves past the horizon when the database clock lags behind it)
  procedure knowledge_time_increases_when_the_clock_lags;

  --%test(Rejects a given knowledge time not after the horizon and stores nothing)
  procedure rejects_a_given_knowledge_time_not_after_the_horizon;

  --%test(A failed call keeps the knowledge horizon)
  procedure a_failed_call_keeps_the_horizon;

  --%test(Changes list the values whose version changed between two knowledge states)
  procedure changes_list_values_whose_version_changed;

  --%test(Changes include a value first known in the later state with no old value)
  procedure changes_include_values_first_known_later;

  --%test(Changes compare the two states, not the versions in between)
  procedure changes_compare_two_states_not_intermediate_versions;

  --%test(Changes between equal knowledge times are empty)
  procedure changes_between_equal_times_are_empty;

  --%test(Changes respect the valid-date range)
  procedure changes_respect_the_valid_date_range;

  --%test(Changes ignore derived values)
  procedure changes_ignore_derived_values;

  --%test(Has curve checks the definition of the curve)
  procedure has_curve_checks_the_definition;
end ut_core_observation;
/
