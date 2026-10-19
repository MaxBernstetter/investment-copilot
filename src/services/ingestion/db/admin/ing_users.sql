--liquibase formatted sql

--changeset yieldlens:ing-owner
--comment: Schema owner of ING. Used only by migrations; owns the tables and packages.
create user ing no authentication
  default tablespace users
  quota unlimited on users;
grant create session, create table, create sequence, create procedure to ing;
--rollback drop user ing cascade;

--changeset yieldlens:ing-app
--comment: Runtime user of the ingestion service. Gets only EXECUTE on the ING packages.
create user ing_app no authentication;
grant create session to ing_app;
--rollback drop user ing_app cascade;

--changeset yieldlens:ing-passwords runOnChange:true
--comment: Passwords come from the environment, so they are set in their own changeset that reruns when they change (rotation).
alter user ing identified by "${ING_PASSWORD}";
alter user ing_app identified by "${ING_APP_PASSWORD}";
