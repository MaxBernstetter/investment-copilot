--liquibase formatted sql

--changeset yieldlens:core-owner
--comment: Schema owner of CORE. Used only by migrations; owns the tables, types and packages.
create user core no authentication
  default tablespace users
  quota unlimited on users;
grant create session, create table, create sequence, create type, create procedure to core;
--rollback drop user core cascade;

--changeset yieldlens:core-app
--comment: Runtime user of the persistence service. Gets only EXECUTE on the CORE packages and types.
create user core_app no authentication;
grant create session to core_app;
--rollback drop user core_app cascade;

--changeset yieldlens:core-passwords runOnChange:true
--comment: Passwords come from the environment, so they are set in their own changeset that reruns when they change (rotation).
alter user core identified by "${CORE_PASSWORD}";
alter user core_app identified by "${CORE_APP_PASSWORD}";
