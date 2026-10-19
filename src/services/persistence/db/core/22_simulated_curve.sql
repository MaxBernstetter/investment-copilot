--liquibase formatted sql

--changeset yieldlens:22-curve-simulated
--comment: Y for a curve of simulated data (scenario mechanism). Simulated and real data never share a curve.
alter table curve add (simulated varchar2(1 char) default 'N' not null);
alter table curve add constraint curve_simulated_ck check (simulated in ('Y', 'N'));
comment on column curve.simulated is 'Y: simulated curve, written only by the scenario mechanism (source_id scenario); N: real source data';
--rollback alter table curve drop column simulated;

--changeset yieldlens:22-curve-ecb-aaa-spot-sim
--comment: Simulated twin of ecb-aaa-spot for scenarios (corrections, late values, gaps, bad values). Never mixed with the real curve.
insert into curve (curve_id, grid_version, rate_type, compounding, unit, source_model, simulated)
values ('ecb-aaa-spot-sim', 1, 'spot', 'continuous', 'percent', null, 'Y');
--rollback delete from curve where curve_id = 'ecb-aaa-spot-sim';
