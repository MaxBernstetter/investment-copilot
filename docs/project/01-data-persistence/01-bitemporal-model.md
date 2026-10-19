# Bitemporal Model

How the `persistence` service stores yield observations in the `CORE` schema so that every value carries a **valid time** and a **knowledge time**. Architecture context: [[03-data-architecture]]. Issues: [#12](https://github.com/MaxBernstetter/investment-copilot/issues/12) (bitemporal storage), [#15](https://github.com/MaxBernstetter/investment-copilot/issues/15) (versioning), [#19](https://github.com/MaxBernstetter/investment-copilot/issues/19) (maturity grid and curve definitions).

## Two time axes

| Axis | Column(s) | Meaning | Set by |
|---|---|---|---|
| Valid time | `valid_date` | The business date the yield applies to | The caller (from the source or the calculation) |
| Knowledge time | `known_from`, `known_to` | The interval in which the platform knew this version | The database |

- A version is visible at knowledge time *t* if `known_from <= t < known_to`.
- `known_to` is `9999-12-31 00:00:00` while the version is **open** (current). Using a sentinel instead of `NULL` keeps the as-of predicate a plain range and lets it use the index.
- Knowledge times are `TIMESTAMP(6)` in **UTC**. `known_from` comes from the database clock (`sys_extract_utc(systimestamp)`), never from the caller's clock. Every version written by one call shares one `known_from`.

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
| `curve` | `curve_id` | The grid version a curve is stored on, and its conventions **as published**: `rate_type` (`spot`, `par`, `forward`), `compounding` (`continuous`, `annual`, `semi-annual`), `unit` (`percent`) and `source_model` (the source's fitting model, optional) |

- **Grid version 1** holds the 11 tenors of phase 1: `3M`, `6M`, `1Y`, `2Y`, `3Y`, `5Y`, `7Y`, `10Y`, `15Y`, `20Y`, `30Y` ([[01-data-sources]]).
- **`ecb-aaa-spot`** is on grid 1 with `spot`, `continuous`, `percent`, `Svensson (ECB)`.
- Conventions are **recorded, not converted**: values are stored as the source publishes them. Converting between conventions (for example semi-annual par yields to continuous spot rates) is a calculation and produces *derived* values in processing.
- Both are seeded by Liquibase changesets (`db/core/19_curve_reference_data.sql`). A new curve or grid version is a new changeset.

Partitioning: interval range partitions of **one month on `valid_date`** (all indexes are local except the primary key). Queries filter by `valid_date`, so they prune partitions.

## PL/SQL interface: package `core_observation`

The service only calls the package; it never touches the table (see [[#Users and privileges]]). The caller owns the transaction; the package never commits.

| Member | Purpose |
|---|---|
| `record_versions(p_versions, o_known_from, o_recorded_count, p_known_from default null)` | Records the elements of `p_versions` (`observation_version_list_t`) as versions, set-based (see [[#Versioning]]). `known_from` is `p_known_from` if given (deterministic tests, replays), otherwise the database clock. Returns the knowledge time and the number of **new** versions. |
| `get_versions(p_curve_id, p_valid_date_from, p_valid_date_to)` | All stored versions of one curve in a valid-date range, as a cursor ordered by `valid_date`, `maturity`, `origin`, `method_version`, `known_from`. Used by tests; as-of retrieval comes with [#22](https://github.com/MaxBernstetter/investment-copilot/issues/22). |
| `open_version_exists` (`-20001`) | Raised when a concurrent call opened the first version of an observation of the batch before this one. Nothing of the batch is stored; the caller retries. |
| `duplicate_observation` (`-20002`) | Raised when an observation appears more than once in the batch. Nothing of the batch is stored. |
| `off_grid_observation` (`-20003`) | Raised when an observation names a curve without a definition in `curve`, or a maturity that is not on its curve's grid. Nothing of the batch is stored. |
| `open_known_to` | The `known_to` sentinel of open versions. |

`observation_version_t` holds the input row: every column of `observation` except `version_id`, `known_from` and `known_to`.

A failed call stores nothing of its batch: `record_versions` rolls back to its own savepoint before it raises.

## Versioning

Values are never overwritten. For each observation of a batch, identified by its key (`curve_id`, `maturity`, `valid_date`, `origin`, `method_version`), `record_versions` compares it with the key's open version:

| Open version | Outcome | Counted as |
|---|---|---|
| none | A new open version | recorded |
| different `value` or `source_id` | The open version is closed (`known_to` = the call's `known_from`) and a new open version is inserted | recorded |
| same `value` and `source_id` | **No-op**: nothing is written; the open version keeps its `run_id`, `change_reason` and `known_from` | unchanged |

- **Version-relevant attributes** are `value` (numerically: `2.61` equals `2.610`) and `source_id`: they state what the value is and where it comes from. `run_id`, `change_reason` and `normalization_version` describe the write, so a reload by another run or another normalization version with the same value and source is unchanged; the open version keeps them as they were.
- Previous versions stay stored with their closed knowledge interval. The intervals of one key are contiguous: each closed `known_to` equals the next version's `known_from`. Every version stays retrievable through `get_versions`; as-of retrieval follows in [#22](https://github.com/MaxBernstetter/investment-copilot/issues/22).
- Reloads are idempotent, so a daily load can resend its whole lookback window ([[12-data-pipeline#Extraction and revisions]]). The stored `change_reason` is the caller's; deriving it belongs to [#23](https://github.com/MaxBernstetter/investment-copilot/issues/23).
- Set-based: one locking `SELECT … FOR UPDATE`, one `UPDATE` (close changed versions) and one `INSERT … SELECT` (open versions for keys without one), each restricted to the batch's valid-date range, so partitions are pruned.

### Concurrency

`record_versions` first locks the open versions of the batch's keys (row locks, no extra privileges) and only then reads the clock. Concurrent writers of the same observations therefore serialize and get increasing knowledge times, and the later writer compares against the earlier one's committed version. Two calls that both record the **first** version of a key can't lock a row; the unique index serializes them and the later one fails with `open_version_exists` (REST `409`); sending the batch again resolves it. The DAG mutex of [[12-data-pipeline#Concurrency control]] keeps such races rare.

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
| `core/` | `CORE` | Tables, index, types, reference data (grid and curves), package (re-applied on change), grants to `CORE_APP` |
| `tests/` | – | utPLSQL test packages; installed by the integration tests only, never migrated |

Liquibase runs from the official `liquibase/liquibase:4.33.0` image, which bundles the Oracle JDBC driver and needs no Java runtime on the host. The nix `liquibase` package (Liquibase 5) wraps only the MySQL, PostgreSQL and Redshift drivers, and Liquibase 5 no longer bundles drivers itself, so it can't reach Oracle without extra jars. Locally, `task persistence:db:migrate` runs it through `src/services/persistence/compose.yaml`; the integration tests run the same image and changelogs against a Testcontainers Oracle.

## Tests

| Level | What | Where |
|---|---|---|
| utPLSQL | `core_observation`: valid and knowledge time, database clock, open versions, provenance, versioning of changed values and sources, contiguous intervals, as-of visibility, unchanged reloads (also with another normalization version), mixed batches, origins and method versions, duplicates, undefined curves and maturities off the grid, empty batch, constraints, range reads | `db/tests/ut_core_observation.pk[sb]`, run by `tests/integration/test_plsql.py` |
| Integration | Migrations (partitioning, package valid, seeded grid and curve conventions, idempotent rerun, no table access for `CORE_APP`), Oracle adapter, REST end to end | `tests/integration/` (Testcontainers, Oracle Free) |
| Unit | Domain rules, use case, REST facade, configuration | `tests/unit/` |

utPLSQL (v3.2.2) is installed into the test container on demand from the pinned, checksum-verified GitHub release and cached under `src/services/persistence/.cache/utplsql`.
