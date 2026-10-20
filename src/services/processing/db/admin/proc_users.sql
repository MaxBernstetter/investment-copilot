--liquibase formatted sql

--changeset yieldlens:proc-owner
--comment: Schema owner of PROC. Used only by migrations; owns the tables and packages.
create user proc no authentication
  default tablespace users
  quota unlimited on users;
grant create session, create table, create sequence, create type, create procedure to proc;
--rollback drop user proc cascade;

--changeset yieldlens:proc-app
--comment: Runtime user of the processing service. Gets only EXECUTE on the PROC packages.
create user proc_app no authentication;
grant create session to proc_app;
--rollback drop user proc_app cascade;

--changeset yieldlens:proc-passwords runOnChange:true
--comment: Passwords come from the environment, so they are set in their own changeset that reruns when they change (rotation).
alter user proc identified by "${PROC_PASSWORD}";
alter user proc_app identified by "${PROC_APP_PASSWORD}";
