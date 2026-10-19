# Bitemporal Model

How the `persistence` service stores yield observations in the `CORE` schema so that every value carries a **valid time** and a **knowledge time**. Architecture context: [[03-data-architecture]]. Issue: [#12](https://github.com/MaxBernstetter/investment-copilot/issues/12).

## Two time axes

| Axis | Column(s) | Meaning | Set by |
|---|---|---|---|
| Valid time | `valid_date` | The business date the yield applies to | The caller (from the source or the calculation) |
| Knowledge time | `known_from`, `known_to` | The interval in which the platform knew this version | The database |

- A version is visible at knowledge time *t* if `known_from <= t < known_to`.
- `known_to` is `9999-12-31 00:00:00` while the version is **open** (current). Using a sentinel instead of `NULL` keeps the as-of predicate a plain range and lets it use the index.
- Knowledge times are `TIMESTAMP(6)` in **UTC**.

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

## Users and privileges

| User | Purpose | Privileges |
|---|---|---|
| `CORE` | Schema owner; used only by migrations | `CREATE SESSION`, `TABLE`, `SEQUENCE`, `TYPE`, `PROCEDURE`; quota on `USERS` |
| `CORE_APP` | Runtime user of the persistence service | `CREATE SESSION`. No table access; it will reach `CORE` only through `EXECUTE` on its packages |

Both users are created by the admin changelog, run as `SYSTEM`. Passwords come from the environment of the migration and are set in their own changeset, which reruns when they change.

## Migrations

Liquibase SQL changelogs under `src/services/persistence/db/`:

| Path | Runs as | Content |
|---|---|---|
| `admin/` | `SYSTEM` | Users `CORE` and `CORE_APP`, grants, passwords |
| `core/` | `CORE` | Table and indexes |

Liquibase runs from the official `liquibase/liquibase:4.33.0` image, which bundles the Oracle JDBC driver and needs no Java runtime on the host. The nix `liquibase` package (Liquibase 5) wraps only the MySQL, PostgreSQL and Redshift drivers, and Liquibase 5 no longer bundles drivers itself, so it can't reach Oracle without extra jars. Locally, `task persistence:db:migrate` runs it through `src/services/persistence/compose.yaml`; the integration tests run the same image and changelogs against a Testcontainers Oracle.

## Tests

| Level | What | Where |
|---|---|---|
| Integration | Migrations (partitioning, idempotent rerun, no table access for `CORE_APP`) | `tests/integration/` (Testcontainers, Oracle Free) |
