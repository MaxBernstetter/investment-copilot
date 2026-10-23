"""The sources the Airflow DAGs load: one ``LoadSource`` per source, as configuration.

Each source gets a daily load DAG and a backfill DAG, built by ``orchestration.load_dags``
from its entry here. A source's pool (``pools.json``) has the same name as its id. The
ingestion job it runs is ``ingestion-load-<source id>`` (see
``docs/project/00-data-ingestion/04-daily-schedule.md``).
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import pendulum

from orchestration.target_calendar import is_target_business_day, previous_target_business_day
from orchestration.us_calendar import is_us_business_day

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


def is_ust_publication_day(run_day: date) -> bool:
    """A UST run loads the day before, which the Treasury publishes only on a US business day."""
    return is_us_business_day(run_day - timedelta(days=1))


def previous_ust_publication_day(run_day: date) -> date:
    """The valid date of a UST run: the day before, published by the Treasury that evening."""
    return run_day - timedelta(days=1)


# The Treasury publishes the curve of a day in the afternoon in New York, so the run the next
# morning in Berlin loads it. Tuesday to Saturday: the runs for Monday to Friday publications.
UST = LoadSource(
    source_id="ust",
    curve_ids=("ust-par",),
    cron="0 8 * * 2-6",
    timezone="Europe/Berlin",
    start_date=datetime(2026, 10, 27, tzinfo=BERLIN),
    is_publication_day=is_ust_publication_day,
    previous_publication_day=previous_ust_publication_day,
    closed_message="the day before {day} was a US bond market holiday: nothing published",
)

SOURCES: tuple[LoadSource, ...] = (ECB, UST)
