--liquibase formatted sql

--changeset yieldlens:23-curve-catalogue-columns
--comment: Catalogue entries of a curve: display label, source, economic area and the attribution its values require.
alter table curve add (
  label       varchar2(128 char),
  source_id   varchar2(64 char),
  area        varchar2(64 char),
  attribution varchar2(256 char)
);
--rollback alter table curve drop (label, source_id, area, attribution);

--changeset yieldlens:23-curve-catalogue-ecb
--comment: Catalogue entries of the ECB AAA curve and its simulated twin (attribution per the ESCB reuse terms).
update curve
   set label = 'ECB euro area AAA spot', source_id = 'ecb', area = 'Euro area',
       attribution = 'Source: ECB statistics'
 where curve_id = 'ecb-aaa-spot';
update curve
   set label = 'ECB euro area AAA spot (scenario data)', source_id = 'scenario', area = 'Euro area',
       attribution = 'Simulated scenario based on ECB statistics'
 where curve_id = 'ecb-aaa-spot-sim';
--rollback update curve set label = null, source_id = null, area = null, attribution = null;

--changeset yieldlens:23-curve-catalogue-not-null
--comment: Every curve carries a catalogue entry; a new curve sets all four columns.
alter table curve modify (label not null, source_id not null, area not null, attribution not null);
--rollback alter table curve modify (label null, source_id null, area null, attribution null);

--changeset yieldlens:23-curve-catalogue-comments
comment on column curve.label is 'Display name of the curve, e.g. ECB euro area AAA spot';
comment on column curve.source_id is 'Source the curve values come from, as in observation.source_id: ecb, or scenario for a simulated curve';
comment on column curve.area is 'Economic area the curve describes, e.g. Euro area';
comment on column curve.attribution is 'Attribution the values require wherever they are shown (ESCB reuse terms); for simulated data a note that it is simulated';
