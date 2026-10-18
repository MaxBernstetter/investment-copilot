--liquibase formatted sql

--changeset yieldlens:19-observation-normalization-version
--comment: Version of the source mapping (normalization rules in ingestion) that produced a published value. Provenance only: it is not version-relevant.
alter table observation add (normalization_version varchar2(64 char));
comment on column observation.normalization_version is 'Version of the normalization rules (source mapping in ingestion) that produced a published value; null if not given';
--rollback alter table observation drop column normalization_version;

--changeset yieldlens:19-observation-version-normalization-version
--comment: The input row carries the normalization version too. Cascade revalidates the list type.
alter type observation_version_t add attribute (normalization_version varchar2(64 char)) cascade;
--rollback alter type observation_version_t drop attribute (normalization_version) cascade;
