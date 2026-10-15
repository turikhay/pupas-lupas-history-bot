from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from throwback.dates import available_years, start_of_day, years_ago

START = date(2017, 11, 5)


@pytest.mark.parametrize(
    ("today", "delta", "expected"),
    [
        (date(2026, 10, 15), 1, date(2025, 10, 15)),
        (date(2024, 2, 29), 1, date(2023, 2, 28)),
        (date(2024, 2, 29), 4, date(2020, 2, 29)),
        (date(2025, 2, 28), 1, date(2024, 2, 28)),
    ],
)
def test_years_ago(today: date, delta: int, expected: date) -> None:
    assert years_ago(delta, today) == expected


@pytest.mark.parametrize(
    ("today", "oldest"),
    [
        (date(2026, 10, 15), date(2018, 10, 15)),  # used to skip 2018
        (date(2026, 11, 4), date(2018, 11, 4)),  # 2017-11-04 is before the start
        (date(2026, 11, 5), date(2017, 11, 5)),  # the start day itself counts
        (date(2026, 12, 31), date(2017, 12, 31)),  # 2017 used to be never reposted
        (date(2028, 2, 29), date(2018, 2, 28)),
    ],
)
def test_available_years_reach_the_start(today: date, oldest: date) -> None:
    years = available_years(today, START)
    assert years == list(range(1, len(years) + 1))
    assert years_ago(years[-1], today) == oldest


@pytest.mark.parametrize("today", [date(2017, 11, 5), date(2018, 11, 4)])
def test_available_years_empty_within_the_first_year(today: date) -> None:
    assert available_years(today, START) == []


def test_start_of_day_is_midnight_in_tz() -> None:
    tz = ZoneInfo("Asia/Yekaterinburg")
    assert start_of_day(date(2019, 1, 1), tz) == datetime(2018, 12, 31, 19, tzinfo=ZoneInfo("UTC"))
