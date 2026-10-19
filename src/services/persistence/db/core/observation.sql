--liquibase formatted sql

--changeset yieldlens:observation-table
--comment: Bitemporal store of yield observations. One row per version; rows are insert-only.
create table observation (
  version_id     number generated always as identity,
  curve_id       varchar2(64 char)  not null,
  maturity       varchar2(16 char)  not null,
  valid_date     date               not null,
  value          number             not null,
  known_from     timestamp(6)       not null,
  known_to       timestamp(6)       default timestamp '9999-12-31 00:00:00' not null,
  origin         varchar2(16 char)  not null,
  method_version varchar2(64 char),
  source_id      varchar2(64 char),
  run_id         varchar2(128 char) not null,
  change_reason  varchar2(16 char)  not null,
  constraint observation_pk primary key (version_id),
  constraint observation_valid_date_ck check (valid_date = trunc(valid_date)),
  constraint observation_knowledge_interval_ck check (known_from < known_to),
  constraint observation_origin_ck check (origin in ('published', 'derived')),
  constraint observation_method_version_ck check (
    (origin = 'published' and method_version is null)
    or (origin = 'derived' and method_version is not null)
  ),
  constraint observation_change_reason_ck check (
    change_reason in ('initial', 'revision', 'correction', 'recalculation', 'simulated')
  )
)
partition by range (valid_date) interval (numtoyminterval(1, 'MONTH')) (
  partition observation_p0 values less than (date '1990-01-01')
);
--rollback drop table observation purge;

--changeset yieldlens:observation-open-version-index
--comment: At most one open version per observation key. Versions of one key never share a knowledge-interval end, so the open version (known_to = 9999-12-31) is unique.
create unique index observation_version_uk on observation (
  curve_id, maturity, valid_date, origin, method_version, known_to
) local;
--rollback drop index observation_version_uk;

--changeset yieldlens:observation-comments
comment on table observation is 'Bitemporal yield observations: one row per version, insert-only except for closing known_to';
comment on column observation.valid_date is 'Valid time: the business date the value applies to';
comment on column observation.value is 'The yield in percent';
comment on column observation.known_from is 'Knowledge time (UTC) from which this version is known; set by the database clock';
comment on column observation.known_to is 'Knowledge time (UTC) until which this version is current; 9999-12-31 while open';
comment on column observation.origin is 'published (from a source) or derived (calculated by YieldLens)';
comment on column observation.method_version is 'Method version of a derived value; null for published values';
comment on column observation.source_id is 'Source the value came from';
comment on column observation.run_id is 'Run that wrote this version';
comment on column observation.change_reason is 'Why this version exists: initial, revision, correction, recalculation, simulated';
