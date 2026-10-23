"""Airflow DAG files for the source loads: one daily load and one backfill DAG per source.

Every source in ``orchestration.sources.SOURCES`` gets its DAGs from the factories in
``orchestration.load_dags``. Adding a source is a config entry there, not a new DAG file.
See ``docs/project/00-data-ingestion/04-daily-schedule.md``.
"""

from orchestration.load_dags import build_backfill_dag, build_daily_load_dag
from orchestration.sources import SOURCES

for _source in SOURCES:
    for _dag in (build_daily_load_dag(_source), build_backfill_dag(_source)):
        globals()[_dag.dag_id] = _dag
