--liquibase formatted sql

--changeset yieldlens:266-curve-ust-par
--comment: The US Treasury daily par yield curve (#266): published par yields, semi-annual bond-equivalent, in percent per annum, on grid 2 for the short bill tenors. Stored unchanged: no conversion.
insert into curve (curve_id, grid_version, rate_type, compounding, unit, source_model, label, source_id, area, attribution)
values ('ust-par', 2, 'par', 'semi-annual', 'percent', null, 'US Treasury par', 'ust', 'United States', 'Source: U.S. Department of the Treasury');
--rollback delete from curve where curve_id = 'ust-par';
