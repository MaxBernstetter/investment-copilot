--liquibase formatted sql

--changeset yieldlens:264-curve-ecb-all-spot
--comment: The ECB euro area all-issuer curve (G_N_C) as the ECB publishes it: spot rates, continuously compounded, in percent per annum, fitted with the Svensson model, on grid 1 like ecb-aaa-spot.
insert into curve (curve_id, grid_version, rate_type, compounding, unit, source_model, label, source_id, area, attribution)
values ('ecb-all-spot', 1, 'spot', 'continuous', 'percent', 'Svensson (ECB)', 'ECB euro area all-issuer spot', 'ecb', 'Euro area', 'Source: ECB statistics');
--rollback delete from curve where curve_id = 'ecb-all-spot';
