--liquibase formatted sql

--changeset yieldlens:ing_app-grants
--comment: The service user reaches ING only through the package interface (no table access).
grant execute on ing_delivery to ing_app;
--rollback revoke execute on ing_delivery from ing_app;
