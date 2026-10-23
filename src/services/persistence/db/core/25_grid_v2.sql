--liquibase formatted sql

--changeset yieldlens:25-grid-maturity-months-fraction
--comment: Months of a tenor may be fractional (1.5M). modify to number(5,2) is rejected by Oracle (ORA-01440) on the populated table, so the column is added, copied, and swapped in. Rollback is valid only while no fractional tenor exists: delete grid version 2 first (changeset 25-grid-maturity-v2).
alter table grid_maturity add (months_new number(5,2));
update grid_maturity set months_new = months;
alter table grid_maturity drop constraint grid_maturity_months_uk;
alter table grid_maturity drop constraint grid_maturity_months_ck;
alter table grid_maturity drop column months;
alter table grid_maturity rename column months_new to months;
alter table grid_maturity modify (months not null);
alter table grid_maturity add constraint grid_maturity_months_uk unique (grid_version, months);
alter table grid_maturity add constraint grid_maturity_months_ck check (months > 0);
--rollback alter table grid_maturity drop constraint grid_maturity_months_uk;
--rollback alter table grid_maturity drop constraint grid_maturity_months_ck;
--rollback alter table grid_maturity add (months_old number(4));
--rollback update grid_maturity set months_old = months;
--rollback alter table grid_maturity drop column months;
--rollback alter table grid_maturity rename column months_old to months;
--rollback alter table grid_maturity modify (months not null);
--rollback alter table grid_maturity add constraint grid_maturity_months_uk unique (grid_version, months);
--rollback alter table grid_maturity add constraint grid_maturity_months_ck check (months > 0);

--changeset yieldlens:25-grid-maturity-v2
--comment: Grid version 2: grid 1 plus the short bill tenors 1M, 1.5M, 2M and 4M (#265). Grid 1 and the curves on it are unchanged.
insert into maturity_grid (grid_version, description)
values (2, 'Grid 1 plus the short bill tenors 1M, 1.5M, 2M and 4M: 15 tenors');
insert into grid_maturity (grid_version, maturity, months)
select 2, maturity, months from grid_maturity where grid_version = 1;
insert into grid_maturity (grid_version, maturity, months) values (2, '1M', 1);
insert into grid_maturity (grid_version, maturity, months) values (2, '1.5M', 1.5);
insert into grid_maturity (grid_version, maturity, months) values (2, '2M', 2);
insert into grid_maturity (grid_version, maturity, months) values (2, '4M', 4);
--rollback delete from grid_maturity where grid_version = 2;
--rollback delete from maturity_grid where grid_version = 2;

--changeset yieldlens:25-grid-maturity-months-comment
--comment: Documents the fractional months.
comment on column grid_maturity.months is 'Length of the tenor in months, for ordering; fractional for short tenors, e.g. 1.5 for 1.5M';
