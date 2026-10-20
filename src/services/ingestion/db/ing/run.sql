--liquibase formatted sql

--changeset yieldlens:run-table
--comment: Run history: one row per attempt of an ingestion job run.
create table run (
  attempt_id      number generated always as identity,
  run_id          varchar2(128 char)  not null,
  attempt         number(5)           not null,
  operation       varchar2(16 char)   not null,
  status          varchar2(16 char)   not null,
  started_at      timestamp(6) default sys_extract_utc(systimestamp) not null,
  finished_at     timestamp(6),
  delivered_count number(12) default 0 not null,
  recorded_count  number(12) default 0 not null,
  unchanged_count number(12) default 0 not null,
  error_type      varchar2(128 char),
  error_message   varchar2(4000 char),
  constraint run_pk primary key (attempt_id),
  constraint run_attempt_uk unique (run_id, attempt),
  constraint run_attempt_ck check (attempt >= 1),
  constraint run_operation_ck check (operation in ('daily', 'history', 'replay')),
  constraint run_status_ck check (status in ('running', 'succeeded', 'partial', 'failed')),
  constraint run_finished_ck check (
    (status = 'running' and finished_at is null)
    or (status <> 'running' and finished_at is not null)),
  constraint run_error_ck check (
    (status in ('running', 'succeeded') and error_type is null and error_message is null)
    or (status in ('partial', 'failed') and error_type is not null)),
  constraint run_counts_ck check (
    delivered_count >= 0 and recorded_count >= 0 and unchanged_count >= 0)
);
--rollback drop table run purge;

--changeset yieldlens:run-started-at-index
create index run_started_at_ix on run (started_at);
--rollback drop index run_started_at_ix;

--changeset yieldlens:run-comments
comment on table run is 'Run history: one row per attempt of an ingestion job run';
comment on column run.attempt_id is 'Surrogate key in start order; the paging cursor';
comment on column run.run_id is 'Stable id of the job run, e.g. daily_load_ecb-2026-10-16';
comment on column run.attempt is '1 for the first attempt of the run id, then one more per retry or rerun';
comment on column run.operation is 'Job operation: daily, history or replay';
comment on column run.status is 'running until finish_run; then succeeded, partial or failed';
comment on column run.started_at is 'When the attempt started (UTC)';
comment on column run.finished_at is 'When the attempt finished (UTC); null while running';
comment on column run.delivered_count is 'Observations the source delivered in this attempt';
comment on column run.recorded_count is 'New versions stored in this attempt';
comment on column run.unchanged_count is 'Values already stored unchanged in this attempt';
comment on column run.error_type is 'Exception type when status is partial or failed';
comment on column run.error_message is 'Exception message when status is partial or failed';
