--liquibase formatted sql

--changeset yieldlens:observation-version-types endDelimiter:/
--comment: Input row and batch of core_observation.record_versions. Knowledge time is not part of the input: the package sets it.
create type observation_version_t as object (
  curve_id       varchar2(64 char),
  maturity       varchar2(16 char),
  valid_date     date,
  value          number,
  origin         varchar2(16 char),
  method_version varchar2(64 char),
  source_id      varchar2(64 char),
  run_id         varchar2(128 char),
  change_reason  varchar2(16 char)
);
/
--rollback drop type observation_version_t;

--changeset yieldlens:observation-version-list-type endDelimiter:/
create type observation_version_list_t as table of observation_version_t;
/
--rollback drop type observation_version_list_t;
