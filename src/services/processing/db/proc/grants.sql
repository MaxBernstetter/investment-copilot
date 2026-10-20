--liquibase formatted sql

--changeset yieldlens:proc_app-grants
--comment: The service user reaches PROC only through proc_quality and its input types.
grant execute on proc_quality to proc_app;
grant execute on proc_day_status_t to proc_app;
grant execute on proc_day_status_list_t to proc_app;
grant execute on proc_value_status_t to proc_app;
grant execute on proc_value_status_list_t to proc_app;
grant execute on proc_finding_t to proc_app;
grant execute on proc_finding_list_t to proc_app;
--rollback revoke execute on proc_quality from proc_app;
--rollback revoke execute on proc_day_status_t from proc_app;
--rollback revoke execute on proc_day_status_list_t from proc_app;
--rollback revoke execute on proc_value_status_t from proc_app;
--rollback revoke execute on proc_value_status_list_t from proc_app;
--rollback revoke execute on proc_finding_t from proc_app;
--rollback revoke execute on proc_finding_list_t from proc_app;
