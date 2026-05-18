"""This file contains classes that give parse the config dictionary and make nice easily type-checkable classes."""



from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, timedelta
import inspect
from io import TextIOWrapper
from math import floor
from pathlib import Path
import sys
import tomllib
from typing import Any, Dict, Generator, Iterable, List, Sequence, Set, Tuple, cast, Iterator, TypeVar
from zoneinfo import ZoneInfo

from error import FluxCardInputError
from output_registry import FormatterProtocol, get_formatter
from segments import Segment


T = TypeVar('T')


### EVER NEED TO HAVE AN ENUMERATED LIST IN REVERSE?
### USE MY FANCY FUNCTION
def reverse_enumerate(sequence: list[T]) -> Iterator[Tuple[int, T]]:
    """Yields (index, item) pairs backwards from the end of a list."""
    return zip(range(len(sequence)-1, -1, -1), reversed(sequence))


def is_date_list_sorted(l: Sequence[date]) -> bool:
    """Checks if a list is sorted in ascending order.
    Returns True if sorted (or empty), False otherwise."""
    # An empty list or single element is always considered sorted
    if len(l) <= 1:
        return True
        
    # Compare each marker with the next one in a single lazy pass
    return all(l[i] <= l[i + 1] for i in range(len(l) - 1))




REPO_ROOT = Path(__file__).resolve().parent.parent

def resolve_config_relative_path(raw_path: str, config_file: Path) -> Path:
    """
    Normalizes a path string from TOML. 
    Absolute paths stay absolute. Relative paths anchor to the config file's directory.
    """
    p = Path(raw_path).expanduser()
    if p.is_absolute():
        return p
    return (config_file.parent / p).resolve()


@dataclass(frozen=True)
class ScheduleConfig(ABC):

    @abstractmethod
    def get_date_filter(self, period_offset: int) -> Tuple[date|None,date|None]: ...

    @classmethod
    def from_dict(cls, raw: Dict[str, Any],manual_schedules_raw: Any) -> "ScheduleConfig":        
        schedule_type = raw.get('type')
        if schedule_type is None:
            raise FluxCardInputError('type required')
        if not isinstance(schedule_type,str):
            raise FluxCardInputError(f'type of type must be a string, got "{schedule_type}')
        
        match schedule_type:
            case 'days_cycle':
                anchor = raw.get("period_anchor")
                if anchor is None:
                    raise FluxCardInputError("period_anchor is required for a days_cycle schedule")
                if not isinstance(anchor,date):
                    raise FluxCardInputError(f"period_anchor must be a date in YYYY-MM-DD format, got '{anchor}'")
                    
                length = raw.get("period_length")
                if length is None:
                    raise FluxCardInputError("period_length is required for a days_cycle schedule")
                if not isinstance(length,int):
                    raise FluxCardInputError(f"period_length must be an int, got '{length}'")
                return DaysCycleConfig(anchor,length)
            case 'monthly':
                start_day = raw.get("start_day")
                if start_day is None:
                    raise FluxCardInputError("start_day is required for a monthly schedule")
                if not isinstance(start_day,int) or not (1 <= start_day <= 28):
                    raise FluxCardInputError(f"start_day must be an int between 1 and 28 inclusive, got '{start_day}'")
                return MonthCycleConfig(start_day)
            case 'manual':
                # have to go pick up the historical markers
                if manual_schedules_raw is None:
                    return ManualCycleConfig([])
                if not isinstance(manual_schedules_raw,dict):
                    raise ValueError('manual schedule markers is not a dictionary')
                markers = cast(Dict[str,Any],manual_schedules_raw).get('markers',[])
                if not isinstance(markers,list):
                    raise ValueError('markers is not a list')
                if not all(isinstance(x,date) for x in markers): # pyright: ignore[reportUnknownVariableType]
                    raise ValueError('not everything in markers is a date')
                if not is_date_list_sorted(cast(List[date],markers)):
                    raise ValueError('markers is not sorted')
                
                return ManualCycleConfig(cast(List[date],markers))
            case _:
                raise FluxCardInputError(f'schedule type "{schedule_type}" is unknown')
        
        assert False, "unreachable"


@dataclass(frozen=True)
class DaysCycleConfig(ScheduleConfig):
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
class MonthCycleConfig(ScheduleConfig):
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
class ManualCycleConfig(ScheduleConfig):
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
            raise FluxCardInputError(f'invalid period {period_offset} in this manual schedule, the past most period is {current_end_index}, the future most period is {current_end_index-len_markers}')

        start_date = None if period_end_index == 0 else self.markers[period_end_index-1]
        end_date = None if period_end_index == len_markers else self.markers[period_end_index]

        return (start_date,end_date)


@dataclass(frozen=True)
class JobConfig:
    # key into the schedules param
    schedule: str | None = field(default=None)
    
    @classmethod
    def from_dict(cls, raw: Dict[str, Any], schedule_keys: Iterable[str]) -> "JobConfig":
        schedule = raw.get("schedule")
        if schedule is not None and (not isinstance(schedule,str) or schedule not in schedule_keys):
            raise FluxCardInputError(f"job schedule must be a valid schedule key string, got '{schedule}'")

        return cls(schedule)

@dataclass(frozen=True)
class OutputConfig(ABC):
    format_key: str 
    format_function: FormatterProtocol
    kwargs: Dict[str,Any]
    
    def execute_output(self, data: Dict[date, List[Segment]]) -> None:
        """Runs the output formatter function"""

        with self.open_stream() as stream:
            self.format_function(stream,data,self.kwargs)


    @abstractmethod
    @contextmanager
    def open_stream(self) -> Generator[TextIOWrapper,None,None]: ...

    @abstractmethod
    def output_str(self) -> str: ...

    @classmethod
    def from_dict(cls, raw: Dict[str,Any], config_path: Path) -> "OutputConfig":
        # output is required, otherwise, how would we know how to output?
        form = raw.pop("format")
        if not isinstance(form,str):
            raise FluxCardInputError(f"format must be a string. Got '{form}'")
        
        dest = raw.pop("dest")

        # give these argument versions for actual parsing, along with the rest of the arguments as is.
        return OutputConfig.from_args(dest,form,config_path,raw)

    @classmethod
    def from_args(cls, dest: str | None, form: str, config_path: Path, extra_kwargs: Dict[str,Any]) -> "OutputConfig":
        # get the formatter
        formatter = get_formatter(form)

        # check the signiture
        sig = inspect.signature(formatter)
        # if the signiture has **kwargs in it, we don't check keys.
        if not any(p.kind == p.VAR_KEYWORD for p in sig.parameters.values()):
            # check the given kwargs for invalid keys (keys not supported by the formatter)
            invalid_keys = set(extra_kwargs.keys()) - set(sig.parameters.keys())
            if invalid_keys:
                raise FluxCardInputError(f'Format "{form}" received unsupported options: {', '.join(invalid_keys)}')
        # we have passed the key check here

        # destination can be None or stdout for stdout
        if dest is None or dest == "stdout":
            return StdoutConfig(form,formatter,extra_kwargs)

        dest_file_path = resolve_config_relative_path(dest, config_path)
        
        return FileConfig(form,formatter,extra_kwargs,dest_file_path)


@dataclass(frozen=True)
class StdoutConfig(OutputConfig):

    @contextmanager
    def open_stream(self) -> Generator[TextIOWrapper,None,None]:
        yield cast(TextIOWrapper,sys.stdout)

    def output_str(self) -> str:
        return 'stdout'

@dataclass(frozen=True)
class FileConfig(OutputConfig):
    file_path: Path

    @contextmanager
    def open_stream(self) -> Generator[TextIOWrapper,None,None]:
        with self.file_path.open("w") as f:
            yield f

    def output_str(self) -> str:
        return str(self.file_path)

@dataclass(frozen=True)
class MacroConfig:
    job_filter: Set[str] | None #= field(default=None)
    period: int | None #= field(default=None)
    outputs: List[OutputConfig] #= cast(List[OutputConfig],field(default_factory=list))

    @classmethod
    def from_dict(cls, raw: Dict[str,Any], config_path: Path) -> "MacroConfig":
        

        job_filter_raw = raw.get('job_filter')
        if job_filter_raw is None:
            job_filter = None
        elif isinstance(job_filter_raw,str):
            job_filter = {job_filter_raw}
        elif isinstance(job_filter_raw,list):
            job_filter = set(cast(List[str],job_filter_raw))
        else:
            raise FluxCardInputError(f"job filter must be a string or list of strings. Got '{job_filter_raw}'")

        # check for _ job which is not allowed.
        if job_filter is not None and '_' in job_filter:
            raise FluxCardInputError("job _ not allowed")

        period = raw.get('period')
        if period is not None and not isinstance(period,int):
            raise FluxCardInputError(f"period must be an int. Got '{period}'")
        
        outputs: List[OutputConfig] = []
        for index, value in enumerate(raw.get('outputs', [])):
            try:
                outputs.append(OutputConfig.from_dict(value,config_path))
            except Exception as e:
                e.add_note(f'in outputs index {index} (0 based)')
                raise e

        return cls(job_filter,period,outputs)


@dataclass(frozen=True)
class AppConfig:
    timecard_path: Path | None = field(default=None)
    output_timezone: ZoneInfo | None = field(default=None)
    default_job: str | None = field(default=None)
    schedules: Dict[str,ScheduleConfig] = cast(Dict[str, ScheduleConfig],field(default_factory=dict))
    jobs: Dict[str, JobConfig] = cast(Dict[str, JobConfig],field(default_factory=dict))
    macros: Dict[str, MacroConfig] = cast(Dict[str, MacroConfig], field(default_factory=dict))
    
    @classmethod
    def from_dict(cls, raw: Dict[str, Any], config_path: Path) -> "AppConfig":

        timecard_path = resolve_config_relative_path(raw["timecard_path"], config_path) if "timecard_path" in raw else None
        
        output_timezone_str = cast(str|None,raw.get("output_timezone"))
        output_timezone = ZoneInfo(output_timezone_str) if output_timezone_str else None

        default_job = raw.get("default_job")
        if default_job is not None and not isinstance(default_job,str):
            raise FluxCardInputError(f"default job must be a string, but got '{default_job}'")
        
        manual_schedules = cast(Dict[str,Any],raw.get('manual_schedule_history',{}))

        schedules: Dict[str,ScheduleConfig] = {}
        for name, value in raw.get("schedules", {}).items():
            try:
                manual_schedule = manual_schedules.get(name,None)
                schedules[name] = ScheduleConfig.from_dict(value,manual_schedule)
            except Exception as e:
                e.add_note(f'in schedule config {name}')
                raise e


        jobs: Dict[str,JobConfig] = {}
        for name, value in raw.get("jobs", {}).items():
            try:
                jobs[name] = JobConfig.from_dict(value, schedules.keys())
            except Exception as e:
                e.add_note(f'in job config {name}')
                raise e

        macros: Dict[str,MacroConfig] = {}
        for name, value in raw.get("macros", {}).items():
            try:
                macros[name] = MacroConfig.from_dict(value,config_path)
            except Exception as e:
                e.add_note(f'in macro {name}')
                raise e

        return cls(
            timecard_path=timecard_path,
            output_timezone = output_timezone,
            default_job=default_job,
            schedules=schedules,
            jobs=jobs,
            macros=macros
        )

    @classmethod
    def load(cls, path: Path) -> "AppConfig":
        with path.open("rb") as f:
            raw = tomllib.load(f)
        return cls.from_dict(raw, path)

    def job_config(self, job_name: str | None) -> JobConfig:
        if job_name is None:
            return JobConfig()
        # if the job is not listed in the config, return a blank one as well
        return self.jobs.get(job_name, JobConfig())
