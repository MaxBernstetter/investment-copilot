--liquibase formatted sql

--changeset yieldlens:20-observation-delivery-id
--comment: Raw source delivery (in ingestion's ING schema) a published value came from. Provenance only: it is not version-relevant.
alter table observation add (delivery_id varchar2(64 char));
comment on column observation.delivery_id is 'Raw source delivery (ingestion reference) a published value came from; null if not given';
--rollback alter table observation drop column delivery_id;

--changeset yieldlens:20-observation-version-delivery-id
--comment: The input row carries the delivery id too. Cascade revalidates the list type.
alter type observation_version_t add attribute (delivery_id varchar2(64 char)) cascade;
--rollback alter type observation_version_t drop attribute (delivery_id) cascade;
