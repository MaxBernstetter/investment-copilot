# Bitemporal Model

How the `persistence` service stores yield observations in the `CORE` schema so that every value carries a **valid time** and a **knowledge time**. Architecture context: [[03-data-architecture]]. Issues: [#12](https://github.com/MaxBernstetter/yield-lens/issues/12) (bitemporal storage), [#15](https://github.com/MaxBernstetter/yield-lens/issues/15) (versioning), [#19](https://github.com/MaxBernstetter/yield-lens/issues/19) (maturity grid and curve definitions).

## Two time axes

| Axis | Column(s) | Meaning | Set by |
|---|---|---|---|
| Valid time | `valid_date` | The business date the yield applies to | The caller (from the source or the calculation) |
| Knowledge time | `known_from`, `known_to` | The interval in which the platform knew this version | The database |

- A version is visible at knowledge time *t* if `known_from <= t < known_to`.
- `known_to` is `9999-12-31 00:00:00` while the version is **open** (current). Using a sentinel instead of `NULL` keeps the as-of predicate a plain range and lets it use the index.
- Knowledge times are `TIMESTAMP(6)` in **UTC**. `known_from` comes from the knowledge clock (see [[#Knowledge clock]]), never from the caller's clock. Every version written by one call shares one `known_from`, and knowledge times strictly increase in commit order.

## Table `observation`

One row per version. Rows are insert-only; the only update is closing `known_to` when a newer version replaces a row (see [[#Versioning]]).

| Column | Type | Null | Meaning |
|---|---|---|---|
| `version_id` | `NUMBER` identity | no | Surrogate key of the version (primary key) |
| `curve_id` | `VARCHAR2(64)` | no | Curve the value belongs to; must be defined in `curve` (see [[#Reference data: maturity grid and curves]]) |
| `maturity` | `VARCHAR2(16)` | no | Tenor code, e.g. `3M`, `10Y`; must be on the curve's grid |
| `valid_date` | `DATE` | no | Valid time (a date, no time part) |
| `value` | `NUMBER` | no | The yield, in the unit and conventions of its curve (`percent` for every curve today) |
| `known_from` | `TIMESTAMP(6)` | no | Start of the knowledge interval (UTC) |
| `known_to` | `TIMESTAMP(6)` | no | End of the knowledge interval (UTC), `9999-12-31` while open |
| `origin` | `VARCHAR2(16)` | no | `published` (from a source) or `derived` (calculated) |
| `method_version` | `VARCHAR2(64)` | yes | Method version of a derived value; `NULL` for published values |
| `source_id` | `VARCHAR2(64)` | yes | Source the value came from |
| `run_id` | `VARCHAR2(128)` | no | Run that wrote the version |
| `change_reason` | `VARCHAR2(16)` | no | `initial`, `revision`, `correction`, `recalculation` or `simulated` |
| `normalization_version` | `VARCHAR2(64)` | yes | Version of the source mapping (normalization rules in ingestion) that produced a published value |
| `delivery_id` | `VARCHAR2(64)` | yes | Raw source delivery (in ingestion's `ING` schema) a published value was parsed from; an opaque reference, no foreign key across schemas |

Constraints:
- `valid_date` has no time part; `known_from < known_to`.
- `origin` and `change_reason` take only the listed values.
- `method_version` is required for `derived` and forbidden for `published`.
- **One open version per observation key:** the unique index `observation_version_uk` on (`curve_id`, `maturity`, `valid_date`, `origin`, `method_version`, `known_to`). The versions of one key never overlap, so their `known_to` values differ and only one can be open.

## Reference data: maturity grid and curves

The common maturity grid and the curve definitions are versioned reference data owned by persistence ([[12-data-pipeline#Reference data]]). They make curves from different sources comparable: every curve is stored on a grid, and its conventions are recorded with it.

| Table | Key | Content |
|---|---|---|
| `maturity_grid` | `grid_version` | A grid version and its description. A version is never changed once applied; a different grid is a new version |
| `grid_maturity` | (`grid_version`, `maturity`) | The tenors of a grid version, with their length in `months` for ordering (unique per version) |
| `curve` | `curve_id` | The grid version a curve is stored on, and its conventions **as published**: `rate_type` (`spot`, `par`, `forward`), `compounding` (`continuous`, `annual`, `semi-annual`), `unit` (`percent`) and `source_model` (the source's fitting model, optional). `simulated` (`Y`/`N`, default `N`) flags a curve of simulated data, written only by the scenario mechanism. Its catalogue entry: `label` (display name), `source_id` (`ecb`, or `scenario` for a simulated curve), `area` (economic area) and `attribution` (required wherever its values are shown). All four are required |

- **Grid version 1** holds the 11 tenors of phase 1: `3M`, `6M`, `1Y`, `2Y`, `3Y`, `5Y`, `7Y`, `10Y`, `15Y`, `20Y`, `30Y` ([[01-data-sources]]).
- **`ecb-all-spot`** is on grid 1 with `spot`, `continuous`, `percent`, `Svensson (ECB)` (#264).
- **`ecb-aaa-spot`** is on grid 1 with `spot`, `continuous`, `percent`, `Svensson (ECB)`. Catalogue entry: label `ECB euro area AAA spot`, source `ecb`, area `Euro area`, attribution `Source: ECB statistics`.
- **`ecb-aaa-spot-sim`** is the simulated twin of `ecb-aaa-spot` on grid 1 (`simulated` = `Y`, no source model). Catalogue entry: label `ECB euro area AAA spot (scenario data)`, source `scenario`, area `Euro area`, attribution `Simulated scenario based on ECB statistics`. Simulated and real data never share a curve: a simulated curve takes only source `scenario`, and source `scenario` only simulated curves (`-20005`).
- Conventions are **recorded, not converted**: values are stored as the source publishes them. Converting between conventions (for example semi-annual par yields to continuous spot rates) is a calculation and produces *derived* values in processing.
- Both are seeded by Liquibase changesets (`db/core/19_curve_reference_data.sql`, and the catalogue entries in `db/core/23_curve_catalogue.sql`). A new curve sets all catalogue columns; a new grid version is a new changeset.

Partitioning: interval range partitions of **one month on `valid_date`** (all indexes are local except the primary key). Queries filter by `valid_date`, so they prune partitions.

## Knowledge clock

Table `knowledge_clock` (`db/core/21_knowledge_clock.sql`) holds one row, `clock_id = 1`, with `known_until`: the **knowledge horizon**, the knowledge time of the latest committed call of `record_versions`. It is seeded with the newest `known_from` of `observation` (`1970-01-01` when empty).

- Every write locks the row first (`SELECT ... FOR UPDATE`), so writers serialize, and then uses a knowledge time after the horizon. The call moves the horizon to its knowledge time when it stores its batch, inside the same transaction. A failed call rolls the move back with its batch.
- The knowledge time is the database clock in UTC, moved to one microsecond after the horizon if the clock lags behind it. A given `p_known_from` must be after the horizon, else `-20004`.
- Because the horizon is the knowledge time of the last commit, a reader can use `knowledge_horizon()` as an as-of time: no later commit adds a version known at or before it, so the answer does not change (see [[#As-of retrieval]]).
- The table has no grants: only the package reads and writes it (definer rights), like the observation table.

Decision and trade-offs: [[0017-commit-safe-knowledge-time]].

## PL/SQL interface: package `core_observation`

The service only calls the package; it never touches the table (see [[#Users and privileges]]). The caller owns the transaction; the package never commits.

| Member | Purpose |
|---|---|
| `record_versions(p_versions, o_known_from, o_recorded_count, p_known_from default null)` | Records the elements of `p_versions` (`observation_version_list_t`) as versions, set-based (see [[#Versioning]]). Locks the knowledge clock first. `known_from` is `p_known_from` if given (deterministic tests, replays; must be after the horizon), otherwise the database clock, moved past the horizon if it lags. Returns the knowledge time and the number of **new** versions. |
| `get_versions(p_curve_id, p_valid_date_from, p_valid_date_to)` | All stored versions of one curve in a valid-date range, as a cursor ordered by `valid_date`, `maturity`, `origin`, `method_version`, `known_from`. Used by tests and the history of a curve. |
| `get_as_of(p_curve_id, p_valid_date, p_as_of)` | The published value of every maturity of the curve's grid as known at `p_as_of` for one valid date, as a cursor with columns `maturity`, `months`, `value`, ordered by `months`. `value` is null where no version is visible; no rows for an undefined curve. See [[#As-of retrieval]]. |
| `get_series(p_curve_id, p_maturity, p_from, p_to, p_as_of)` | The published value of one maturity for each valid date in the inclusive range `p_from`..`p_to` as known at `p_as_of`, as a cursor with columns `valid_date`, `value`, ordered by `valid_date`. Only dates with a visible version have a row, so dates without one leave gaps. See [[#As-of retrieval]]. |
| `get_value_versions(p_curve_id, p_maturity, p_valid_date, p_as_of)` | The published versions of one value known at `p_as_of`, as a cursor with columns `version_id`, `value`, `known_from`, `known_to`, `source_id`, `run_id`, `change_reason`, `normalization_version`, `delivery_id`, ordered by `known_from`. Versions first known after `p_as_of` are left out; `known_to` is null for a version still current at `p_as_of`. No rows for an unknown value. Derived values are not included. |
| `get_changes(p_curve_id, p_from, p_to, p_since, p_as_of)` | The published values of one curve whose visible version differs between two knowledge states, for valid dates in the inclusive range `p_from`..`p_to`, as a cursor with columns `valid_date`, `maturity`, `old_value`, `new_value`, `change_reason`, `source_id`, `known_from`, ordered by `valid_date` and grid order. `old_value` is the value known at `p_since` (null if none); `new_value` and the other columns describe the version known at `p_as_of`. States are compared, not the versions in between, so a value changed and changed back shows old = new. Derived values are not included. |
| `has_maturity(p_curve_id, p_maturity)` | `1` if the maturity is on the curve's grid, else `0` (also `0` for an undefined curve). |
| `has_curve(p_curve_id)` | `1` if the curve is defined, else `0`. |
| `get_curves()` | The curve catalogue: every defined curve with its catalogue entry, conventions and grid, as a cursor with columns `curve_id`, `label`, `source_id`, `area`, `attribution`, `rate_type`, `compounding`, `unit`, `source_model`, `simulated`, `maturity`, `months`; one row per curve and grid maturity, ordered by `curve_id`, `months`. |
| `latest_valid_date(p_curve_id, p_as_of)` | The latest valid date with a published value visible at `p_as_of`; null if none. |
| `current_knowledge_time()` | The database clock now in UTC (`sys_extract_utc(systimestamp)`). It is not the knowledge time a write gets; see [[#Knowledge clock]]. |
| `knowledge_horizon()` | The committed knowledge horizon: the knowledge time of the latest committed call. Does not lock. |
| `open_version_exists` (`-20001`) | Raised when a concurrent call opened the first version of an observation of the batch before this one. Nothing of the batch is stored; the caller retries. |
| `duplicate_observation` (`-20002`) | Raised when an observation appears more than once in the batch. Nothing of the batch is stored. |
| `off_grid_observation` (`-20003`) | Raised when an observation names a curve without a definition in `curve`, or a maturity that is not on its curve's grid. Nothing of the batch is stored. |
| `knowledge_time_not_increasing` (`-20004`) | Raised when a given `p_known_from` is not after the knowledge horizon. Nothing of the batch is stored. |
| `simulated_mismatch` (`-20005`) | Raised when an observation of a simulated curve has a source other than `scenario`, or an observation with source `scenario` names a real curve. Nothing of the batch is stored. |
| `open_known_to` | The `known_to` sentinel of open versions. |

`observation_version_t` holds the input row: every column of `observation` except `version_id`, `known_from` and `known_to`.

A failed call stores nothing of its batch and does not move the horizon: `record_versions` rolls back to its own savepoint before it raises.

## Versioning

Values are never overwritten. For each observation of a batch, identified by its key (`curve_id`, `maturity`, `valid_date`, `origin`, `method_version`), `record_versions` compares it with the key's open version:

| Open version | Outcome | Counted as |
|---|---|---|
| none | A new open version | recorded |
| different `value` or `source_id` | The open version is closed (`known_to` = the call's `known_from`) and a new open version is inserted | recorded |
| same `value` and `source_id` | **No-op**: nothing is written; the open version keeps its `run_id`, `change_reason` and `known_from` | unchanged |

- **Version-relevant attributes** are `value` (numerically: `2.61` equals `2.610`) and `source_id`: they state what the value is and where it comes from. `run_id`, `change_reason`, `normalization_version` and `delivery_id` describe the write, so a reload by another run, another normalization version or from another delivery with the same value and source is unchanged; the open version keeps them as they were.
- Previous versions stay stored with their closed knowledge interval. The intervals of one key are contiguous: each closed `known_to` equals the next version's `known_from`. Every version stays retrievable through `get_versions`, and the version visible at a given time through [[#As-of retrieval]].
- **Change reason:** a new version keeps the `change_reason` the caller sent, with one exception. An `initial` version of an observation that already has a version (closed or open) is stored as `revision`, so a revised value from a rerun is a revision without the caller having to know it. The first version keeps `initial`; `correction`, `recalculation` and `simulated` are stored as sent. An unchanged reload is a no-op, so its reason is not stored.
- Reloads are idempotent, so a daily load can resend its whole lookback window ([[12-data-pipeline#Extraction and revisions]]).
- Set-based: one locking `SELECT … FOR UPDATE` of the open versions, one `UPDATE` (close changed versions) and one `INSERT … SELECT` (open versions for keys without one), each restricted to the batch's valid-date range, so partitions are pruned.

### Concurrency

`record_versions` locks the knowledge clock row first, then the open versions of the batch's keys (row locks, no extra privileges). Every write takes the clock lock, so all writers serialize, and each one sees the committed state of the writers before it. The clock lock makes knowledge times increase in commit order, so no commit can land at a knowledge time a reader has already used. The cost is that writes do not overlap; this fits the daily batch loads.

Two calls that both record the **first** version of a key can't lock an open version row; with the clock lock they serialize anyway. The unique index still guards the key, and a call that loses the race fails with `open_version_exists` (REST `409`); sending the batch again resolves it. The DAG mutex of [[12-data-pipeline#Concurrency control]] keeps such races rare.

## As-of retrieval

A consumer asks *what did the curve look like on valid date `d` as it was known at time `t`?* The answer is read with `get_as_of`:

- **Visibility:** a version is visible at `t` if `known_from <= t < known_to`. Revisions therefore never change an answer for an earlier time: a value that was revised at `t2` is still returned for any `t` before `t2`.
- **Published only:** `origin = 'published'`. Derived values are not part of the as-of answer; they have their own method versions.
- **Grid order:** every maturity of the curve's grid is returned, ordered by `months`. A maturity without a visible value comes back with a null `value`, so the shape of the curve never depends on which values were known.
- **Undefined curve:** no rows. The service turns that into not found.
- **Watermark:** `knowledge_horizon()` is the latest committed knowledge time. A read at `t <= knowledge_horizon()` is safe: every write committed later gets a knowledge time after the horizon it read, so it cannot appear at `t`. This holds because writes lock the knowledge clock ([[#Knowledge clock]]).
- **Effective knowledge time:** the service reads at `min(t, knowledge_horizon())`, or at the horizon when no `t` is given. A `t` after the horizon is therefore answered at the horizon, and the response echoes the time it was answered at. A `t` after the database clock is rejected (`422`) before the horizon is consulted.

The service reads the latest valid date known at the effective time with `latest_valid_date` when no valid date is given.

A series reads one maturity over a range of valid dates with `get_series`. It applies the same visibility and published-only rules per valid date, so a valid date revised after `t` still shows its value as of `t`, and a valid date with no version visible at `t` is absent from the result rather than null. `knowledge_horizon` supplies the default knowledge time and the cap on a requested one (see [[#As-of retrieval]]); `current_knowledge_time` is only the bound that rejects a time in the future.

## Users and privileges

| User | Purpose | Privileges |
|---|---|---|
| `CORE` | Schema owner; used only by migrations | `CREATE SESSION`, `TABLE`, `SEQUENCE`, `TYPE`, `PROCEDURE`; quota on `USERS` |
| `CORE_APP` | Runtime user of the persistence service | `CREATE SESSION`; `EXECUTE` on `core_observation` and its two types. No table access |

Both users are created by the admin changelog, run as `SYSTEM`. Passwords come from the environment of the migration and are set in their own changeset, which reruns when they change.

## Migrations

Liquibase SQL changelogs under `src/services/persistence/db/`:

| Path | Runs as | Content |
|---|---|---|
| `admin/` | `SYSTEM` | Users `CORE` and `CORE_APP`, grants, passwords |
| `core/` | `CORE` | Tables (observation, knowledge clock), index, types, reference data (grid and curves), package (re-applied on change), grants to `CORE_APP` |
| `tests/` | – | utPLSQL test packages; installed by the integration tests only, never migrated |

Liquibase runs from the official `liquibase/liquibase:4.33.0` image, which bundles the Oracle JDBC driver and needs no Java runtime on the host. The nix `liquibase` package (Liquibase 5) wraps only the MySQL, PostgreSQL and Redshift drivers, and Liquibase 5 no longer bundles drivers itself, so it can't reach Oracle without extra jars. Locally, `task persistence:db:migrate` runs it through `src/services/persistence/compose.yaml`; the integration tests run the same image and changelogs against a Testcontainers Oracle.

## Tests

| Level | What | Where |
|---|---|---|
| utPLSQL | `core_observation`: valid and knowledge time, database clock, open versions, provenance, versioning of changed values and sources, contiguous intervals, as-of visibility, series reads per maturity, grid membership, the knowledge clock (horizon, clock lag, rejected and failed calls), unchanged reloads (also with another normalization version or delivery), mixed batches, simulated curves (scenario source only, mixing rejected), origins and method versions, duplicates, undefined curves and maturities off the grid, empty batch, constraints, range reads | `db/tests/ut_core_observation.pk[sb]`, run by `tests/integration/test_plsql.py` |
| Integration | Migrations (partitioning, package valid, seeded grid, curve conventions and knowledge clock, idempotent rerun, no table access for `CORE_APP`), knowledge clock (an as-of read at the horizon is unchanged by a write committed later), Oracle adapter, REST end to end | `tests/integration/` (Testcontainers, Oracle Free) |
| Unit | Domain rules, use case, REST facade, configuration | `tests/unit/` |

utPLSQL (v3.2.2) is installed into the test container on demand from the pinned, checksum-verified GitHub release and cached under `src/services/persistence/.cache/utplsql`.
