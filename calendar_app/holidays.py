from dataclasses import dataclass
from datetime import date

from holidays import country_holidays


@dataclass(frozen=True)
class Holiday:
    date: date
    title: str


def us_holidays(start, end):
    holidays = country_holidays('US', years=range(start.year, end.year + 1), observed=True)
    dates = [day for day in sorted(holidays) if start <= day <= end]
    return [
        Holiday(day, title)
        for day in dates
        for title in holidays.get_list(day)
    ]
