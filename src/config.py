"""This file contains classes that give parse the config dictionary and make nice easily type-checkable classes."""



from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
import inspect
from math import floor
from pathlib import Path
import tomllib
from typing import Any, Callable, Dict, Iterable, Iterator, List, NoReturn, Sequence, Set, Tuple, TypeGuard, TypeVar, Union, cast
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from error import FluxCardInputTypeError, FluxCardInputValueError
from monads import Box, Maybe
from output_registry import get_formatter
from output_runners import FileRunner, OutputRunner, StdoutRunner

# Define the allowed scalar types from the TOML specification
TomlScalar = Union[str, int, float, bool, datetime, date, time]

TomlType = Union[
    TomlScalar,
    List["TomlType"],
    Dict[str, "TomlType"]
]

TomlTable = Dict[str, TomlType]
TomlArray = List[TomlType]




T = TypeVar('T')

### EVER NEED TO HAVE AN ENUMERATED LIST IN REVERSE?
### USE MY FANCY FUNCTION
def reverse_enumerate(sequence: list[T]) -> Iterator[Tuple[int, T]]:
    """Yields (index, item) pairs backwards from the end of a list."""
    return zip(range(len(sequence)-1, -1, -1), reversed(sequence))


def is_list_dates(l: List[Any]) -> TypeGuard[List[date]]:
    return all(isinstance(x,date) for x in l)

def is_list_strings(l: List[Any]) -> TypeGuard[List[str]]:
    return all(isinstance(x,date) for x in l)


def is_date_list_sorted(l: Sequence[date]) -> bool:
    """Checks if a list is sorted in ascending order.
    Returns True if sorted (or empty), False otherwise."""
    # An empty list or single element is always considered sorted
    if len(l) <= 1:
        return True
        
    # Compare each marker with the next one in a single lazy pass
    return all(l[i] <= l[i + 1] for i in range(len(l) - 1))



def raise_type_error(key: str, got_type: str, expected_type: str, more_info: str = '') -> NoReturn:
    raise FluxCardInputTypeError(f'type error at {key}, expected type {expected_type}, but got type {got_type}{f'\n{more_info}' if more_info else ''}')

def raise_value_error(key: str, value: Any, error: str) -> NoReturn:
    raise FluxCardInputValueError(f'value error at {key}, expected {error}, but got {value}')

def raise_required_field_error(key: str) -> NoReturn:
    raise FluxCardInputValueError(f'{key} field required')

from typing import Callable, TypeVar, Any

K = TypeVar("K")
V = TypeVar("V")
R = TypeVar("R")

def with_key_note(
    note_factory: Callable[[K], str], 
    action: Callable[[K, V], R]
) -> Callable[[K, V], R]:
    """
    Wraps an item-processing closure, dynamically generating and 
    attaching a traceback note using the item's runtime key.
    """
    def wrapper(key: K, value: V) -> R:
        try:
            return action(key, value)
        except Exception as e:
            # Build the specific note string using the loop's key on the fly
            dynamic_note = note_factory(key)
            e.add_note(dynamic_note)
            raise e
    return wrapper



def dict_for_each(function: Callable[[str,TomlType],T]) -> Callable[[Dict[str,TomlType]],Dict[str,T]]:
    return lambda x: {key: function(key,value) for key, value in x.items()}

def list_for_each(function: Callable[[int,TomlType],T]) -> Callable[[List[TomlType]],List[T]]:
    return lambda x: [function(i,value) for i,value in enumerate(x)]



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
    def from_dict(cls, raw: TomlTable,manual_schedules_raw: TomlType|None) -> "ScheduleConfig":
        try:
            schedule_type = (
                Box(raw.get('type'))
                .map(lambda x: x if x is not None else raise_required_field_error('type'))
                .map(lambda x: x if isinstance(x,str) else raise_type_error('type',type(x).__name__,'str'))
                .unwrap()
            )
        except Exception as e:
            e.add_note('at key type')
            raise e
        
        match schedule_type:
            case 'days_cycle':
                try:
                    anchor = (
                        Box(raw.get('period_anchor'))
                        .map(lambda x: x if x is not None else raise_required_field_error('period_anchor'))
                        .map(lambda x: x if isinstance(x,date) else raise_type_error('days_cycle',type(x).__name__,'date'))
                        .unwrap()
                    )
                except Exception as e:
                    e.add_note('at key period_anchor')
                    raise e

                try:
                    length = (
                        Box(raw.get('period_length'))
                        .map(lambda x: x if x is not None else raise_required_field_error('period_length'))
                        .map(lambda x: x if isinstance(x,int) else raise_type_error('period_length',type(x).__name__,'int'))
                        .unwrap()
                    )
                except Exception as e:
                    e.add_note('at key period_length')
                    raise e

                return DaysCycleConfig(anchor,length)
            case 'monthly':
                try:
                    start_day = (
                        Box(raw.get('start_day'))
                        .map(lambda x: x if x is not None else raise_required_field_error('start_day'))
                        .map(lambda x: x if isinstance(x,int) else raise_type_error('start_day',type(x).__name__,'int'))
                        .map(lambda x: x if (1 <= x <= 28) else raise_value_error('start_day',x,'a value between 1 and 28 inclusive'))
                        .unwrap()
                    )
                except Exception as e:
                    e.add_note('at key start_day')
                    raise e
                    
                return MonthCycleConfig(start_day)
            case 'manual':
                # have to go pick up the historical markers
                markers = (
                    Maybe(manual_schedules_raw)
                    .map(lambda x: x if isinstance(x,dict) else raise_type_error('manual_schedule_history.[job_name]',type(x).__name__,'dict'))
                    .map(lambda x: x.get('markers',[]))
                    .map(lambda x: x if isinstance(x,list) else raise_type_error('markers',type(x).__name__,'list'))
                    .map(lambda x: x if is_list_dates(x) else raise_type_error('markers',type(x).__name__,'list of dates'))
                    .map(lambda x: x if is_date_list_sorted(x) else raise_value_error('markers',x,'the list to be sorted'))
                    .unwrap_or(list)
                )
                
                return ManualCycleConfig(markers)
            case _:
                raise FluxCardInputValueError(f'Unknown schedule type {schedule_type} at key schedule')
        
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
            raise_value_error('period',period_offset,f'a value between {current_end_index} and {current_end_index-len_markers} for this manual schedule')
            # raise FluxCardInputValueError(f'invalid period {period_offset} in this manual schedule, the past most period is {current_end_index}, the future most period is {current_end_index-len_markers}')

        start_date = None if period_end_index == 0 else self.markers[period_end_index-1]
        end_date = None if period_end_index == len_markers else self.markers[period_end_index]

        return (start_date,end_date)


@dataclass(frozen=True)
class JobConfig:
    # key into the schedules param
    schedule: str | None # = field(default=None)
    
    @classmethod
    def from_dict(cls, raw: TomlTable, schedule_keys: Iterable[str]) -> "JobConfig":
        try:
            schedule = (
                Maybe(raw.get('schedule'))
                .map(lambda x: x if isinstance(x,str) else raise_type_error('schedule',type(x).__name__,'str'))
                .map(lambda x: x if x in schedule_keys else raise_value_error('schedule',x,f'a key in schedules {schedule_keys}'))
                .unwrap()
            )
        except Exception as e:
            e.add_note('at key schedule')
            raise e

        return cls(schedule)


def parse_output_runner_from_dict(raw: TomlTable, config_path: Path) -> OutputRunner:
    # output is required, otherwise, how would we know how to output?
    try:
        form = (
            Box(raw.get('format'))
            .map(lambda x: x if x is not None else raise_required_field_error('format'))
            .map(lambda x: x if isinstance(x, str) else raise_type_error('format',type(x).__name__,'str'))
            .unwrap()
        )
    except Exception as e:
        e.add_note('at key format')
        raise e
    # remove the key from the dictionary
    raw.pop('format')
    try:
        dest = Box(raw.get('dest','stdout')).map(lambda x: x if isinstance(x, str) else raise_type_error('dest',type(x).__name__,'str')).unwrap()
    except Exception as e:
        e.add_note('at key dest')
        raise e
    # remove the key from the dictionary
    try:
        raw.pop("dest")
    except:
        pass

    # give these argument versions for actual parsing, along with the rest of the arguments as is.
    return _parse_output_runner_common(dest,form,config_path,raw)

def parse_output_runner_from_args(dest: str, form: str, config_path: Path, extra_kwargs: TomlTable) -> OutputRunner:
    return _parse_output_runner_common(dest,form,config_path,extra_kwargs)


def _parse_output_runner_common(dest: str, form: str, config_path: Path, extra_kwargs: TomlTable) -> OutputRunner:
    # get the formatter
    formatter = get_formatter(form)

    # check the signiture
    sig = inspect.signature(formatter)
    # if the signiture has **kwargs in it, we don't check keys.
    if not any(p.kind == p.VAR_KEYWORD for p in sig.parameters.values()):
        # check the given kwargs for invalid keys (keys not supported by the formatter)
        invalid_keys = set(extra_kwargs.keys()) - set(sig.parameters.keys())
        if invalid_keys:
            raise FluxCardInputValueError(f'Format "{form}" received unsupported options: {', '.join(invalid_keys)}')
    # we have passed the key check here

    # destination can be None or stdout for stdout
    if dest == "stdout":
        return StdoutRunner(form,formatter,extra_kwargs)

    dest_file_path = resolve_config_relative_path(dest, config_path)
    
    return FileRunner(form,formatter,extra_kwargs,dest_file_path)




@dataclass(frozen=True)
class MacroConfig:
    job_filter: Set[str] | None #= field(default=None)
    period: int | None #= field(default=None)
    output_runners: List[OutputRunner]

    @classmethod
    def from_dict(cls, raw: TomlTable, config_path: Path) -> "MacroConfig":
        try:
            job_filter = (
                Maybe(raw.get('job_filter'))
                .map(lambda x: {x} if isinstance(x,str) else 
                            set(x) if isinstance(x,list) and is_list_strings(x)
                            else raise_type_error('job_filter',type(x).__name__,'str or list of str'))
                .map(lambda x: x if '_' not in x else raise_value_error('job_filter',x,'any other string besides an underscore. Underscore is reserved for command line clearing the filter'))
                .unwrap()
            )
        except Exception as e:
            e.add_note('at key job_filter')
            raise e

        try:
            period = (
                Maybe(raw.get('period'))
                .map(lambda x: x if isinstance(x,int) else raise_type_error('period',type(x).__name__,'int'))
                .unwrap()
            )
        except Exception as e:
            e.add_note('at key period')
            raise e

        try:
            outputs = (
                Box(raw.get('outputs',[]))
                .map(lambda x: x if isinstance(x,list) else raise_type_error('outputs',type(x).__name__,'list'))
                .map(list_for_each(with_key_note(lambda i: f'in output {i}',lambda i,x: parse_output_runner_from_dict(x,config_path) if isinstance(x,dict) else raise_type_error(f'outputs.{i}',type(x).__name__,'dict'))))
                .unwrap()
            )
        except Exception as e:
            e.add_note('at key outputs')
            raise e

        return cls(job_filter,period,outputs)


@dataclass(frozen=True)
class AppConfig:
    timecard_path: Path | None # = field(default=None)
    output_timezone: ZoneInfo | None # = field(default=None)
    default_job: str | None # = field(default=None)
    schedules: Dict[str,ScheduleConfig] # = cast(Dict[str, ScheduleConfig],field(default_factory=dict))
    jobs: Dict[str, JobConfig] # = cast(Dict[str, JobConfig],field(default_factory=dict))
    macros: Dict[str, MacroConfig] # = cast(Dict[str, MacroConfig], field(default_factory=dict))
    
    @classmethod
    def from_dict(cls, raw: TomlTable, config_path: Path) -> "AppConfig":
        try:
            timecard_path = (
                Maybe(raw.get('timecard_path'))
                .map(lambda x: x if isinstance(x,str) else raise_type_error('timecard_path',type(x).__name__,'str'))
                .map(lambda x: resolve_config_relative_path(x,config_path))
                .unwrap()
            )
        except Exception as e:
            e.add_note('at key timecard_path')
            raise e

        try:
            output_timezone = (
                Maybe(raw.get('output_timezone'))
                .map(lambda x: x if isinstance(x,str) else raise_type_error('output_timezone',type(x).__name__,'str'))
                .map(ZoneInfo)
                .unwrap()
            )
        except (ValueError, ZoneInfoNotFoundError) as e:
            e.add_note('at key output_timezone')
            raise FluxCardInputValueError(e)
            
        except Exception as e:
            e.add_note('at key output_timezone')
            raise e

        try:
            default_job = (
                Maybe(raw.get('default_job'))
                .map(lambda x: x if isinstance(x,str) else raise_type_error('default_job',type(x).__name__,'str'))
                .unwrap()
            )
        except Exception as e:
            e.add_note('at key default_job')
            raise e

        try:
            manual_schedules = (
                Maybe(raw.get('manual_schedule_history'))
                .map(lambda x: x if isinstance(x,dict) else raise_type_error('manual_schedule_history',type(x).__name__,'dict'))
                .unwrap_or(dict)
            )
        except Exception as e:
            e.add_note('at table manual_schedule_history')
            raise e

        try:
            schedules = (
                Maybe(raw.get('schedules'))
                .map(lambda x: x if isinstance(x,dict) else raise_type_error('schedules',type(x).__name__,'dict'))
                .map(dict_for_each(with_key_note(lambda k: f'in schedule {k}',lambda k,v: (ScheduleConfig.from_dict(v,manual_schedules.get(k)) if isinstance(v,dict) else raise_type_error(f'schedules.{k}',type(v).__name__,'dict')))))
                .unwrap_or(dict)
            )
        except Exception as e:
            e.add_note('at table schedules')
            raise e
        
        schedule_keys = schedules.keys()

        try:
            jobs = (
                Maybe(raw.get('jobs'))
                .map(lambda x: x if isinstance(x,dict) else raise_type_error('jobs',type(x).__name__,'dict'))
                .map(dict_for_each(with_key_note(lambda k: f'in job {k}',lambda k,v: (JobConfig.from_dict(v,schedule_keys) if isinstance(v,dict) else raise_type_error(f'jobs.{k}',type(v).__name__,'dict')))))
                .unwrap_or(dict)
            )
        except Exception as e:
            e.add_note('at table jobs')
            raise e

        try:
            macros = (
                Maybe(raw.get('macros'))
                .map(lambda x: x if isinstance(x,dict) else raise_type_error('macros',type(x).__name__,'dict'))
                .map(dict_for_each(with_key_note(lambda k: f'in macro {k}',lambda k,v: (MacroConfig.from_dict(v,config_path) if isinstance(v,dict) else raise_type_error(f'macros.{k}',type(v).__name__,'dict')))))
                .unwrap_or(dict)
            )
        except Exception as e:
            e.add_note('at key macros')
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
            raw = cast(TomlTable,tomllib.load(f))
        return cls.from_dict(raw, path)

    def job_config(self, job_name: str | None) -> JobConfig:
        if job_name is None:
            return JobConfig(None)
        # if the job is not listed in the config, return a blank one as well
        return self.jobs.get(job_name, JobConfig(None))
