from datetime import datetime
from zoneinfo import ZoneInfo

from access.facade.rest.caching import cache_control

BERLIN = ZoneInfo("Europe/Berlin")
KNOWN = datetime(2026, 3, 13, 9, 0, tzinfo=BERLIN)
IMMUTABLE = "public, max-age=31536000, immutable"


def test_an_as_of_echoed_unchanged_is_immutable() -> None:
    assert cache_control(KNOWN, KNOWN) == IMMUTABLE


def test_no_requested_as_of_must_be_revalidated() -> None:
    assert cache_control(None, KNOWN) == "no-cache"


def test_an_answer_earlier_than_the_request_must_be_revalidated() -> None:
    later = datetime(2026, 3, 13, 10, 0, tzinfo=BERLIN)

    assert cache_control(later, KNOWN) == "no-cache"


def test_the_same_instant_in_another_offset_is_settled() -> None:
    in_utc = datetime(2026, 3, 13, 8, 0, tzinfo=ZoneInfo("UTC"))

    assert cache_control(in_utc, KNOWN) == IMMUTABLE
    assert cache_control(KNOWN, in_utc) == IMMUTABLE


def test_an_incomplete_answer_must_be_revalidated() -> None:
    assert cache_control(KNOWN, KNOWN, complete=False) == "no-cache"
