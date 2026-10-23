"""The sources the Airflow DAGs load: one ``LoadSource`` per source, as configuration.

Each source gets a daily load DAG and a backfill DAG, built by ``orchestration.load_dags``
from its entry here. A source's pool (``pools.json``) has the same name as its id. The
ingestion job it runs is ``ingestion-load-<source id>`` (see
``docs/project/00-data-ingestion/04-daily-schedule.md``).
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime

import pendulum

from orchestration.target_calendar import is_target_business_day, previous_target_business_day

BERLIN = pendulum.timezone("Europe/Berlin")


@dataclass(frozen=True, slots=True)
class LoadSource:
    source_id: str  # also the pool name and the suffix of the job command
    curve_ids: tuple[str, ...]  # the curves the load writes; each is quality-checked
    cron: str  # when the daily load runs
    timezone: str  # the timezone of ``cron`` and of the run-day arithmetic
    start_date: datetime  # tz-aware start of the daily DAG
    is_publication_day: Callable[[date], bool]
    previous_publication_day: Callable[[date], date]
    closed_message: str  # the skip message of a closed day; ``{day}`` is the run day

    @property
    def pool(self) -> str:
        return self.source_id

    @property
    def job_command(self) -> str:
        return f"ingestion-load-{self.source_id}"


ECB = LoadSource(
    source_id="ecb",
    curve_ids=("ecb-aaa-spot", "ecb-all-spot"),
    cron="15 13 * * 1-5",
    timezone="Europe/Berlin",
    start_date=datetime(2026, 10, 19, tzinfo=BERLIN),
    is_publication_day=is_target_business_day,
    previous_publication_day=previous_target_business_day,
    closed_message="{day} is a TARGET holiday: the ECB publishes nothing",
)

SOURCES: tuple[LoadSource, ...] = (ECB,)
