--liquibase formatted sql

--changeset yieldlens:19-maturity-grid-table
--comment: Versioned common maturity grid. A grid version is never changed once applied; a new grid is a new version.
create table maturity_grid (
  grid_version number(4)          not null,
  description  varchar2(200 char) not null,
  constraint maturity_grid_pk primary key (grid_version),
  constraint maturity_grid_version_ck check (grid_version > 0)
);
--rollback drop table maturity_grid purge;

--changeset yieldlens:19-grid-maturity-table
--comment: The maturities (tenors) of each grid version, with their length in months for ordering.
create table grid_maturity (
  grid_version number(4)         not null,
  maturity     varchar2(16 char) not null,
  months       number(4)         not null,
  constraint grid_maturity_pk primary key (grid_version, maturity),
  constraint grid_maturity_months_uk unique (grid_version, months),
  constraint grid_maturity_grid_fk foreign key (grid_version) references maturity_grid,
  constraint grid_maturity_months_ck check (months > 0)
);
--rollback drop table grid_maturity purge;

--changeset yieldlens:19-curve-table
--comment: Curve definitions: the grid a curve is stored on and its conventions as published. Conventions are recorded, never converted.
create table curve (
  curve_id     varchar2(64 char) not null,
  grid_version number(4)         not null,
  rate_type    varchar2(16 char) not null,
  compounding  varchar2(16 char) not null,
  unit         varchar2(16 char) not null,
  source_model varchar2(64 char),
  constraint curve_pk primary key (curve_id),
  constraint curve_grid_fk foreign key (grid_version) references maturity_grid,
  constraint curve_rate_type_ck check (rate_type in ('spot', 'par', 'forward')),
  constraint curve_compounding_ck check (compounding in ('continuous', 'annual', 'semi-annual')),
  constraint curve_unit_ck check (unit in ('percent'))
);
--rollback drop table curve purge;

--changeset yieldlens:19-reference-data-comments
comment on table maturity_grid is 'Versioned common maturity grid; rows of an applied version never change';
comment on table grid_maturity is 'Maturities (tenors) of a grid version';
comment on column grid_maturity.maturity is 'Tenor code as stored in observation.maturity, e.g. 3M, 10Y';
comment on column grid_maturity.months is 'Length of the tenor in months, for ordering';
comment on table curve is 'Curve definitions: grid and conventions of a curve as published, recorded and not converted';
comment on column curve.rate_type is 'spot (zero-coupon), par or forward';
comment on column curve.compounding is 'Compounding convention of the values: continuous, annual or semi-annual';
comment on column curve.unit is 'Unit of observation.value: percent (per annum)';
comment on column curve.source_model is 'Model the source fitted the curve with, e.g. Svensson (ECB); null if none';

--changeset yieldlens:19-maturity-grid-v1
--comment: Grid version 1: the 11 tenors of phase 1 (docs/project/00-data-ingestion/01-data-sources.md).
insert into maturity_grid (grid_version, description)
values (1, 'Common grid of phase 1: 3M to 30Y, 11 tenors');
insert into grid_maturity (grid_version, maturity, months) values (1, '3M', 3);
insert into grid_maturity (grid_version, maturity, months) values (1, '6M', 6);
insert into grid_maturity (grid_version, maturity, months) values (1, '1Y', 12);
insert into grid_maturity (grid_version, maturity, months) values (1, '2Y', 24);
insert into grid_maturity (grid_version, maturity, months) values (1, '3Y', 36);
insert into grid_maturity (grid_version, maturity, months) values (1, '5Y', 60);
insert into grid_maturity (grid_version, maturity, months) values (1, '7Y', 84);
insert into grid_maturity (grid_version, maturity, months) values (1, '10Y', 120);
insert into grid_maturity (grid_version, maturity, months) values (1, '15Y', 180);
insert into grid_maturity (grid_version, maturity, months) values (1, '20Y', 240);
insert into grid_maturity (grid_version, maturity, months) values (1, '30Y', 360);
--rollback delete from grid_maturity where grid_version = 1;
--rollback delete from maturity_grid where grid_version = 1;

--changeset yieldlens:19-curve-ecb-aaa-spot
--comment: The ECB euro area AAA curve as the ECB publishes it: spot rates, continuously compounded, in percent per annum, fitted with the Svensson model.
insert into curve (curve_id, grid_version, rate_type, compounding, unit, source_model)
values ('ecb-aaa-spot', 1, 'spot', 'continuous', 'percent', 'Svensson (ECB)');
--rollback delete from curve where curve_id = 'ecb-aaa-spot';
