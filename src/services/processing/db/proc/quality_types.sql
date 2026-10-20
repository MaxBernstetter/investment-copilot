--liquibase formatted sql

--changeset yieldlens:proc-day-status-types endDelimiter:/
--comment: Input row and batch for proc_quality.record_check day statuses.
create type proc_day_status_t as object (
  valid_date date,
  status     varchar2(8 char)
);
/
--rollback drop type proc_day_status_t;

--changeset yieldlens:proc-day-status-list-type endDelimiter:/
create type proc_day_status_list_t as table of proc_day_status_t;
/
--rollback drop type proc_day_status_list_t;

--changeset yieldlens:proc-value-status-types endDelimiter:/
--comment: Input row and batch for proc_quality.record_check value statuses.
create type proc_value_status_t as object (
  version_id number,
  maturity   varchar2(16 char),
  valid_date date,
  status     varchar2(8 char)
);
/
--rollback drop type proc_value_status_t;

--changeset yieldlens:proc-value-status-list-type endDelimiter:/
create type proc_value_status_list_t as table of proc_value_status_t;
/
--rollback drop type proc_value_status_list_t;

--changeset yieldlens:proc-finding-types endDelimiter:/
--comment: Input row and batch for proc_quality.record_check findings.
create type proc_finding_t as object (
  valid_date  date,
  maturity    varchar2(16 char),
  version_id  number,
  rule        varchar2(32 char),
  severity    varchar2(8 char),
  value       number,
  explanation varchar2(400 char),
  evidence    varchar2(400 char)
);
/
--rollback drop type proc_finding_t;

--changeset yieldlens:proc-finding-list-type endDelimiter:/
create type proc_finding_list_t as table of proc_finding_t;
/
--rollback drop type proc_finding_list_t;
