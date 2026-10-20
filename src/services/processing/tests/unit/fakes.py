from datetime import UTC, date, datetime

from processing.domain.assessment import CheckedDay, ValueStatus
from processing.domain.quality import Finding, Rule, Severity, Status

AS_OF = datetime(2026, 10, 9, 8, 0, tzinfo=UTC)
FROM = date(2026, 10, 7)
TO = date(2026, 10, 7)


class FakeQualityStore:
    def __init__(self) -> None:
        self.is_database_reachable = True
        self.checked: list[CheckedDay] = [
            CheckedDay(FROM, Status.WARN, "run-1", AS_OF),
        ]
        self.stored_findings: list[Finding] = [
            Finding(
                Rule.MISSING_DATE,
                Severity.WARN,
                FROM,
                None,
                None,
                None,
                "No value was published for this TARGET business day.",
                "No value for any maturity on 2026-10-07",
            )
        ]
        self.maturity_filter: str | None = None

    async def is_ready(self) -> bool:
        return self.is_database_reachable

    async def current_time(self) -> datetime:
        return AS_OF

    async def checked_days(
        self, curve_id: str, valid_from: date, valid_to: date, as_of: datetime
    ) -> list[CheckedDay]:
        return self.checked

    async def findings(
        self,
        curve_id: str,
        valid_from: date,
        valid_to: date,
        as_of: datetime,
        *,
        maturity: str | None = None,
    ) -> list[Finding]:
        return self.stored_findings

    async def value_statuses(
        self,
        curve_id: str,
        valid_from: date,
        valid_to: date,
        as_of: datetime,
        *,
        maturity: str | None = None,
    ) -> list[ValueStatus]:
        self.maturity_filter = maturity
        return [ValueStatus(1, "10Y", FROM, Status.WARN)]
