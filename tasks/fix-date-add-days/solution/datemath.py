def _is_leap(year):
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def _days_in_month(year, month):
    if month == 2:
        return 29 if _is_leap(year) else 28
    if month in (4, 6, 9, 11):
        return 30
    return 31


def add_days(year, month, day, n):
    """Add n days to the date (year, month, day) and return the new
    (year, month, day) tuple. Handles month and year rollover."""
    for _ in range(n):
        day += 1
        if day > _days_in_month(year, month):
            day = 1
            month += 1
            if month > 12:
                month = 1
                year += 1
    return (year, month, day)
