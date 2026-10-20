# Data Architecture

## Database

- **Oracle Database Free 23ai**, one instance (see [[0001-oracle-plsql]]). The `gvenzl/oracle-free:23-*` images now report release 23.26 as "Oracle AI Database 26ai Free", Oracle's new name for the same release line.
- **One schema per service:** `ING`, `CORE`, `PROC`. Each schema has its own least-privilege users, with no cross-schema grants (see [[0002-service-per-bounded-context]]): the schema owner (e.g. `CORE`), used only by migrations, and a runtime user (e.g. `CORE_APP`) with `EXECUTE` on the schema's packages and nothing else.
- Each schema also holds the service's own transparency data: runs, lineage and business alerts (see [[10-observability]]).
- `access` and `frontend` own no schema.
- Airflow uses a separate Postgres instance for its own metadata only.

## Bitemporal model (`CORE`)

Every version of an observation is a row; rows are never updated in place except to close their knowledge interval.

| Column | Meaning |
|---|---|
| `curve_id`, `maturity`, `valid_date` | What the value describes (valid time) |
| `value` | The yield |
| `known_from`, `known_to` | Knowledge interval (UTC, set by the database clock); `known_to` is `9999-12-31` (open) for the current version |
| `origin` | `published` or `derived` (+ `method_version`) |
| `source_id`, `run_id`, `delivery_id` | Provenance (`delivery_id`: the raw delivery in `ING` the value came from) |
| `change_reason` | Initial, revision, correction, recalculation, simulated |

- Details of the implemented model: [[01-bitemporal-model]].
- **As-of rule:** a version is visible at knowledge time *t* if `known_from <= t < known_to`.
- **Integrity:** at most one open version per (`curve_id`, `maturity`, `valid_date`, `origin`, `method_version`).
- **Simulated data** (scenario mechanism) lives on separate simulated curves (`simulated` = `Y`, e.g. `ecb-aaa-spot-sim`) and is written with source `scenario` only. The store rejects any batch that mixes simulated and real data. Simulated data is isolated, not removed: real curves are never touched.
- **Reproducibility:** each version references the run that wrote it. The run records the source schema version, normalization version, method version, reference-data version and image SHA (see [[12-data-pipeline]]).
- **Concurrency:** write packages lock per curve and valid-date range, so overlapping writers serialize.

## PL/SQL as the schema API

- Each schema exposes **PL/SQL packages** as its interface, for example `core_observation.record_versions`, `core_observation.get_as_of`, and `core_observation.diff`.
- The Python service calls the packages; it never runs ad-hoc DML against tables.
- Versioning and as-of logic live in one place, inside the database, close to the data.

## Marts (`PROC`)

- Quality results of the `processing` service (see [[02-processing-service]] in the data processing project notes): `check_run` (one per curve, valid range and knowledge time; rerunning the same key replaces its children), `checked_day`, `value_quality` and `quality_finding`. `value_quality` refers to the persistence version it assessed by an opaque `version_id` with no foreign key, since CORE is another schema.
- Consumer-ready marts: curves (current and as-of), spreads/slope, quality.
- They are built from data that processing reads via the persistence interfaces (bulk Arrow), never by cross-schema SQL.
- Marts are partitioned and published by **write–audit–publish**: build into a staging table, validate, then partition exchange (see [[0011-validation-gates-and-wap]]).
- At scale, refresh is incremental per affected partition (see [[08-scalability]]).

## Lifecycle

- Retention per data type, partition compression for old data, and backups are defined in [[12-data-pipeline]] and [[0012-backup-and-restore]].
- Raw payloads and core versions are never deleted; they are the replay source and the audit trail.

## Oracle and PL/SQL standards

- **Package design:** business logic in packages (spec = interface, body = implementation); no business logic in triggers; no dynamic SQL without bind variables.
- **Bulk processing:** set-based SQL first; `BULK COLLECT` / `FORALL` for row sets; no row-by-row loops over large sets.
- **Errors:** defined exceptions with application error codes; no `WHEN OTHERS THEN NULL`.
- **Instrumentation:** `DBMS_APPLICATION_INFO` (module/action) set per call; trace id passed from the service as `CLIENT_IDENTIFIER`.
- **Tests:** utPLSQL unit tests per package, run in CI against an Oracle Free container.
- **Migrations:**
  - Liquibase SQL changelogs per schema, versioned with the service, applied on deploy. Never edit applied changesets.
  - Liquibase runs from the `liquibase/liquibase` Docker image, which bundles the Oracle JDBC driver. Users and grants live in a separate admin changelog run as `SYSTEM`.
  - Changes follow **expand/contract**: old and new code (e.g. a running job on the previous image) must both work during a deploy.
- **Naming:** `snake_case`; tables singular (`observation`), packages named `<schema>_<aggregate>`.
