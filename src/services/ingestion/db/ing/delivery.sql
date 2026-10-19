--liquibase formatted sql

--changeset yieldlens:delivery-table
--comment: Raw source deliveries: one row per answered source request, payload byte for byte. Insert-only.
create table delivery (
  delivery_id     number generated always as identity,
  source_id       varchar2(64 char)   not null,
  run_id          varchar2(128 char)  not null,
  request_url     varchar2(4000 char) not null,
  response_status number(3)           not null,
  fetched_at      timestamp(6)        not null,
  last_modified   timestamp(6),
  etag            varchar2(512 char),
  payload         blob,
  payload_sha256  varchar2(64 char),
  constraint delivery_pk primary key (delivery_id),
  constraint delivery_response_status_ck check (response_status between 100 and 599),
  constraint delivery_payload_sha256_ck check (
    (payload is null and payload_sha256 is null)
    or (
      payload is not null
      and payload_sha256 is not null
      and regexp_like(payload_sha256, '^[0-9a-f]{64}$')
    )
  )
)
lob (payload) store as securefile
partition by range (fetched_at) interval (numtoyminterval(1, 'MONTH')) (
  partition delivery_p0 values less than (timestamp '2000-01-01 00:00:00')
);
--rollback drop table delivery purge;

--changeset yieldlens:delivery-comments
comment on table delivery is 'Raw source deliveries (bronze): one row per answered source request, insert-only; the replay source';
comment on column delivery.request_url is 'Full request URL including the query string';
comment on column delivery.response_status is 'HTTP status of the answer, e.g. 200, 304 or the source''s 404 "no data"';
comment on column delivery.fetched_at is 'When ingestion received the answer (UTC)';
comment on column delivery.last_modified is 'Last-Modified of the answer (UTC): the source''s publication time, never a knowledge time';
comment on column delivery.etag is 'ETag of the answer, if any';
comment on column delivery.payload is 'Response body byte for byte; null for an empty delivery (no data, not modified, empty body)';
comment on column delivery.payload_sha256 is 'SHA-256 of the payload (lowercase hex), computed by ingestion; null without payload';
