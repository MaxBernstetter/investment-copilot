--liquibase formatted sql

--changeset yieldlens:proc-check-run-table
--comment: One quality check run: the natural key is (curve, valid range, knowledge time). Recording the same key again replaces the run's children.
create table check_run (
  check_run_id      number generated always as identity,
  run_id            varchar2(128 char) not null,
  curve_id          varchar2(64 char)  not null,
  valid_from        date               not null,
  valid_to          date               not null,
  checked_as_of     timestamp(6)       not null,
  rule_set_version  varchar2(16 char)  not null,
  recorded_at       timestamp(6) default sys_extract_utc(systimestamp) not null,
  constraint check_run_pk primary key (check_run_id),
  constraint check_run_uk unique (curve_id, valid_from, valid_to, checked_as_of),
  constraint check_run_range_ck check (valid_from <= valid_to)
);
--rollback drop table check_run purge;

--changeset yieldlens:proc-checked-day-table
--comment: Day status of a checked run: the worst severity of the day's findings, or passed.
create table checked_day (
  check_run_id  number              not null,
  curve_id      varchar2(64 char)   not null,
  valid_date    date                not null,
  status        varchar2(8 char)    not null,
  constraint checked_day_pk primary key (check_run_id, valid_date),
  constraint checked_day_check_run_fk foreign key (check_run_id) references check_run (check_run_id),
  constraint checked_day_status_ck check (status in ('passed', 'info', 'warn'))
);
create index checked_day_curve_date_ix on checked_day (curve_id, valid_date);
--rollback drop table checked_day purge;

--changeset yieldlens:proc-value-quality-table
--comment: Status of each value of a checked run, keyed by the persistence version it assessed.
create table value_quality (
  check_run_id  number              not null,
  version_id    number              not null,
  curve_id      varchar2(64 char)   not null,
  maturity      varchar2(16 char)   not null,
  valid_date    date                not null,
  status        varchar2(8 char)    not null,
  constraint value_quality_pk primary key (check_run_id, version_id),
  constraint value_quality_check_run_fk foreign key (check_run_id) references check_run (check_run_id),
  constraint value_quality_status_ck check (status in ('passed', 'info', 'warn'))
);
create index value_quality_run_date_ix on value_quality (check_run_id, valid_date);
--rollback drop table value_quality purge;

--changeset yieldlens:proc-quality-finding-table
--comment: One finding of a checked run: the rule that flagged it, its severity and the text shown to users.
create table quality_finding (
  finding_id    number generated always as identity,
  check_run_id  number              not null,
  curve_id      varchar2(64 char)   not null,
  valid_date    date                not null,
  maturity      varchar2(16 char),
  version_id    number,
  rule          varchar2(32 char)   not null,
  severity      varchar2(8 char)    not null,
  value         number,
  explanation   varchar2(400 char)  not null,
  evidence      varchar2(400 char)  not null,
  constraint quality_finding_pk primary key (finding_id),
  constraint quality_finding_check_run_fk foreign key (check_run_id) references check_run (check_run_id),
  constraint quality_finding_rule_ck check (rule in ('range', 'jump', 'missing-date', 'missing-maturity')),
  constraint quality_finding_severity_ck check (severity in ('info', 'warn'))
);
create index quality_finding_run_date_ix on quality_finding (check_run_id, valid_date);
--rollback drop table quality_finding purge;

--changeset yieldlens:proc-quality-comments
comment on table check_run is 'Quality check runs (PROC): one per curve, valid range and knowledge time; rerunning the same key replaces its children';
comment on column check_run.run_id is 'Caller-chosen run identifier, e.g. check-quality-<curve>-<from>-<to>';
comment on column check_run.checked_as_of is 'Knowledge time (UTC) the check read the curve at; the same time as the persistence as-of of the read';
comment on column check_run.rule_set_version is 'Version of the rule set that produced the results (see the plausibility thresholds)';
comment on column check_run.recorded_at is 'When the run was recorded (UTC)';
comment on table checked_day is 'Status of each business day of a checked run (passed, info or warn)';
comment on table value_quality is 'Status of each value of a checked run; version_id is the persistence version it assessed';
comment on column value_quality.version_id is 'Opaque persistence reference (the version of the value in CORE); no foreign key, persistence owns it';
comment on table quality_finding is 'Findings of a checked run: the rule, severity, value and the explanation and evidence shown to users';
comment on column quality_finding.maturity is 'Maturity of the value the finding concerns; null for day-level findings';
comment on column quality_finding.version_id is 'Opaque persistence reference of the value; null for day-level findings; no foreign key';
comment on column quality_finding.explanation is 'What the rule means, in words a user can read';
comment on column quality_finding.evidence is 'The concrete facts that triggered the finding';
