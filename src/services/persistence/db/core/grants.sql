--liquibase formatted sql

--changeset yieldlens:core_app-grants
--comment: The service user reaches CORE only through the package interface (no table access).
grant execute on core_observation to core_app;
grant execute on observation_version_t to core_app;
grant execute on observation_version_list_t to core_app;
--rollback revoke execute on core_observation from core_app;
--rollback revoke execute on observation_version_t from core_app;
--rollback revoke execute on observation_version_list_t from core_app;
