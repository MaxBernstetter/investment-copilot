# Bitemporal Model

How the `persistence` service stores yield observations in the `CORE` schema so that every value carries a **valid time** and a **knowledge time**. Architecture context: [[03-data-architecture]]. Issue: [#12](https://github.com/MaxBernstetter/investment-copilot/issues/12).

## Two time axes

| Axis | Column(s) | Meaning | Set by |
|---|---|---|---|
| Valid time | `valid_date` | The business date the yield applies to | The caller (from the source or the calculation) |
| Knowledge time | `known_from`, `known_to` | The interval in which the platform knew this version | The database |

- A version is visible at knowledge time *t* if `known_from <= t < known_to`.
- `known_to` is `9999-12-31 00:00:00` while the version is **open** (current). Using a sentinel instead of `NULL` keeps the as-of predicate a plain range and lets it use the index.
- Knowledge times are `TIMESTAMP(6)` in **UTC**. `known_from` comes from the database clock (`sys_extract_utc(systimestamp)`), never from the caller's clock. Every version written by one call shares one `known_from`.

## Table `observation`

One row per version. Rows are insert-only; the only update that will ever happen is closing `known_to` when a newer version replaces a row (versioning, [#15](https://github.com/MaxBernstetter/investment-copilot/issues/15)).

| Column | Type | Null | Meaning |
|---|---|---|---|
| `version_id` | `NUMBER` identity | no | Surrogate key of the version (primary key) |
| `curve_id` | `VARCHAR2(64)` | no | Curve the value belongs to |
| `maturity` | `VARCHAR2(16)` | no | Tenor code, e.g. `3M`, `10Y`, `1Y6M` |
| `valid_date` | `DATE` | no | Valid time (a date, no time part) |
| `value` | `NUMBER` | no | The yield in percent |
| `known_from` | `TIMESTAMP(6)` | no | Start of the knowledge interval (UTC) |
| `known_to` | `TIMESTAMP(6)` | no | End of the knowledge interval (UTC), `9999-12-31` while open |
| `origin` | `VARCHAR2(16)` | no | `published` (from a source) or `derived` (calculated) |
| `method_version` | `VARCHAR2(64)` | yes | Method version of a derived value; `NULL` for published values |
| `source_id` | `VARCHAR2(64)` | yes | Source the value came from |
| `run_id` | `VARCHAR2(128)` | no | Run that wrote the version |
| `change_reason` | `VARCHAR2(16)` | no | `initial`, `revision`, `correction`, `recalculation` or `simulated` |

Constraints:
- `valid_date` has no time part; `known_from < known_to`.
- `origin` and `change_reason` take only the listed values.
- `method_version` is required for `derived` and forbidden for `published`.
- **One open version per observation key:** the unique index `observation_version_uk` on (`curve_id`, `maturity`, `valid_date`, `origin`, `method_version`, `known_to`). The versions of one key never overlap, so their `known_to` values differ and only one can be open.

Partitioning: interval range partitions of **one month on `valid_date`** (all indexes are local except the primary key). Queries filter by `valid_date`, so they prune partitions.

## PL/SQL interface: package `core_observation`

The service only calls the package; it never touches the table (see [[#Users and privileges]]). The caller owns the transaction; the package never commits.

| Member | Purpose |
|---|---|
| `record_versions(p_versions, o_known_from, o_recorded_count, p_known_from default null)` | Inserts every element of `p_versions` (`observation_version_list_t`) as a new open version in one set-based `INSERT … SELECT`. `known_from` is `p_known_from` if given (deterministic tests, replays), otherwise the database clock. Returns the knowledge time and the number of versions. |
| `get_versions(p_curve_id, p_valid_date_from, p_valid_date_to)` | All stored versions of one curve in a valid-date range, as a cursor ordered by `valid_date`, `maturity`, `origin`, `method_version`, `known_from`. Used by tests; as-of retrieval comes with [#22](https://github.com/MaxBernstetter/investment-copilot/issues/22). |
| `open_version_exists` (`-20001`) | Raised when an observation of the batch already has an open version or appears twice in it. Nothing of the batch is stored. |
| `open_known_to` | The `known_to` sentinel of open versions. |

`observation_version_t` holds the input row: every column of `observation` except `version_id`, `known_from` and `known_to`.

### Scope of this first slice

- Recording a value whose key already has an open version is **rejected**, not versioned. Closing the open version on a changed value and treating an unchanged value as a no-op belong to versioning ([#15](https://github.com/MaxBernstetter/investment-copilot/issues/15)): it replaces the `open_version_exists` path inside `record_versions` and keeps the table, the types and the call signature.
- The per-curve lock of [[12-data-pipeline#Concurrency control]] is not needed yet: concurrent inserts of the same key already serialize on the unique index. It comes with versioning, when a write reads before it closes a version.

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
| `core/` | `CORE` | Table, index, types, package (re-applied on change), grants to `CORE_APP` |
| `tests/` | – | utPLSQL test packages; installed by the integration tests only, never migrated |

Liquibase runs from the official `liquibase/liquibase:4.33.0` image, which bundles the Oracle JDBC driver and needs no Java runtime on the host. The nix `liquibase` package (Liquibase 5) wraps only the MySQL, PostgreSQL and Redshift drivers, and Liquibase 5 no longer bundles drivers itself, so it can't reach Oracle without extra jars. Locally, `task persistence:db:migrate` runs it through `src/services/persistence/compose.yaml`; the integration tests run the same image and changelogs against a Testcontainers Oracle.

## Tests

| Level | What | Where |
|---|---|---|
| utPLSQL | `core_observation`: valid and knowledge time, database clock, open versions, provenance, conflicts, empty batch, constraints, range reads | `db/tests/ut_core_observation.pk[sb]`, run by `tests/integration/test_plsql.py` |
| Integration | Migrations (partitioning, package valid, idempotent rerun, no table access for `CORE_APP`) | `tests/integration/` (Testcontainers, Oracle Free) |

utPLSQL (v3.2.2) is installed into the test container on demand from the pinned, checksum-verified GitHub release and cached under `src/services/persistence/.cache/utplsql`.
