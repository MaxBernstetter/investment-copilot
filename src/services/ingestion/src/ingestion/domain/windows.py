"""Valid-date windows that a load requests from a source."""

from dataclasses import dataclass
from datetime import date, timedelta

SATURDAY = 5


@dataclass(frozen=True, slots=True)
class DateWindow:
    """An inclusive range of valid dates."""

    start: date
    end: date

    def __post_init__(self) -> None:
        if self.start > self.end:
            raise ValueError(f"window start {self.start} is after its end {self.end}")


def lookback_window(valid_date: date, lookback_business_days: int) -> DateWindow:
    """The window of a daily load: ``valid_date`` and the business days before it.

    Business days are Monday to Friday. A holiday inside the window only means one
    observation date fewer, so the source calendar is not needed here.
    """
    if lookback_business_days < 0:
        raise ValueError("lookback_business_days must not be negative")
    start = valid_date
    remaining = lookback_business_days
    while remaining > 0:
        start -= timedelta(days=1)
        if start.weekday() < SATURDAY:
            remaining -= 1
    return DateWindow(start, valid_date)


def yearly_windows(history: DateWindow) -> list[DateWindow]:
    """Split a history range into one window per calendar year, in order."""
    return [
        DateWindow(max(history.start, date(year, 1, 1)), min(history.end, date(year, 12, 31)))
        for year in range(history.start.year, history.end.year + 1)
    ]
