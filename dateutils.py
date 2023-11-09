from datetime import date, datetime, tzinfo

def today_at(tz: tzinfo) -> date:
    now = datetime.now(tz)
    return date(now.year, now.month, now.day)

def to_datetime(d: date, tz: tzinfo) -> datetime:
    return datetime(d.year, d.month, d.day, 0, 0, 0, 0, tz)

def years_ago(delta: int, today: date):
    target_year = today.year - delta
    target_day = today.day
    if not is_leap_year(target_year) and today.month == 2 and today.day == 29:
        target_day = 28
    return date(today.year - delta, today.month, target_day)

def is_leap_year(year: int) -> bool:
    if (year % 4) == 0:
        if (year % 100) == 0:
            if (year % 400) == 0:
                return True
            else:
                return False
        else:
            return True
    else:     
        return False

if __name__ == '__main__':
    for i in range(1, 30):
        d = years_ago(i, date(2024, 2, 29))
        print(d)
        print(is_leap_year(d.year))
