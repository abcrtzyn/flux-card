from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, timedelta
from math import floor
from typing import Iterator, List, Tuple, TypeVar

from error import FluxCardInputError




T = TypeVar('T')

### EVER NEED TO HAVE AN ENUMERATED LIST IN REVERSE?
### USE MY FANCY FUNCTION
def reverse_enumerate(sequence: list[T]) -> Iterator[Tuple[int, T]]:
    """Yields (index, item) pairs backwards from the end of a list."""
    return zip(range(len(sequence)-1, -1, -1), reversed(sequence))



@dataclass(frozen=True)
class Schedule(ABC):

    @abstractmethod
    def get_date_filter(self, period_offset: int) -> Tuple[date|None,date|None]: ...

@dataclass(frozen=True)
class DaysCycleSchedule(Schedule):
    period_anchor: date
    period_length: int

    def get_date_filter(self, period_offset: int) -> Tuple[date, date]:
        # how many days since the anchor (can be negative)
        days_since_anchor = (date.today() - self.period_anchor).days
        # which period is today a part of?
        current_period_index = floor(days_since_anchor / self.period_length)
        # offset index by the user's input (0 current, 1 previous, so on)
        target_period_index = current_period_index - period_offset
        # shift that many days from the anchor
        start_date = self.period_anchor + timedelta(days=target_period_index*self.period_length)
        end_date = start_date + timedelta(days=self.period_length)
        return (start_date, end_date)
        

@dataclass(frozen=True)
class MonthCycleSchedule(Schedule):
    # a day between 1 to 28 that marks the beginning of the pay period.
    start_day: int

    def get_date_filter(self, period_offset: int) -> Tuple[date, date]:
        today = date.today()
        # using year*12 + (month-1) as a easy way to calulate month based stuff.
        # Jan of 2026 would be 24312, Feb of 2026 would be 24313

        # getting the current month index
        # also, if the day of the period hasn't past yet, we are in previous month's period
        current_index = today.year * 12 + (today.month - 1) - (today.day < self.start_day)
        # this will get the month that we are asking for
        period_index = current_index - period_offset
        # convert back to year and month for this month
        period_start_year, period_start_month = divmod(period_index,12)
        period_start_month += 1
        # and next month
        period_end_year, period_end_month = divmod(period_index+1,12)
        period_end_month += 1
        # and figure out the start date and end date
        start_date = date(period_start_year, period_start_month, self.start_day)
        end_date = date(period_end_year, period_end_month, self.start_day)
        
        return (start_date, end_date)



@dataclass(frozen=True)
class ManualCycleSchedule(Schedule):
    markers: List[date]

    def get_date_filter(self, period_offset: int) -> Tuple[date | None, date | None]:
        today = date.today()
        len_markers = len(self.markers)

        # starting at the end
        # looking for the first marker less than or equal to today
        for i, marker in reverse_enumerate(self.markers):
            if marker <= today:
                current_end_index = i+1
                break
        else:
            current_end_index = 0
        # current_end_index is the list index of the end date of the current period

        # period_end_index is the list index of the end date of the target period
        period_end_index = current_end_index - period_offset

        if period_end_index < 0 or period_end_index > len_markers:
            raise FluxCardInputError('period',period_offset,f'a value between {current_end_index} and {current_end_index-len_markers} for this manual schedule')

        start_date = None if period_end_index == 0 else self.markers[period_end_index-1]
        end_date = None if period_end_index == len_markers else self.markers[period_end_index]

        return (start_date,end_date)
