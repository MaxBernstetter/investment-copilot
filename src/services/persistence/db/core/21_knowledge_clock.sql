--liquibase formatted sql

--changeset yieldlens:21-knowledge-clock
--comment: The committed knowledge horizon: the knowledge time of the latest committed write. One row; record_versions locks it on every write, so knowledge times strictly increase and an as-of read at the horizon never changes after a later commit.
create table knowledge_clock (
  clock_id    number(1)     default 1 not null,
  known_until timestamp(6)  not null,
  constraint knowledge_clock_pk primary key (clock_id),
  constraint knowledge_clock_single_row_ck check (clock_id = 1)
);
insert into knowledge_clock
  select 1, coalesce(max(known_from), timestamp '1970-01-01 00:00:00') from observation;
--rollback drop table knowledge_clock purge;
