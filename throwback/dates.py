import calendar
from datetime import date, datetime, tzinfo


def today_at(tz: tzinfo) -> date:
    return datetime.now(tz).date()


def start_of_day(d: date, tz: tzinfo) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=tz)


def years_ago(delta: int, today: date) -> date:
    year = today.year - delta
    day = today.day
    if today.month == 2 and today.day == 29 and not calendar.isleap(year):
        day = 28
    return date(year, today.month, day)


def available_years(today: date, start: date) -> list[int]:
    # How many years ago the same day was, for every such day on or after start
    return [delta for delta in range(1, today.year - start.year + 1) if years_ago(delta, today) >= start]
