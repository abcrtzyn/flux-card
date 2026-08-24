"""This file contains classes that give parse the config dictionary and make nice easily type-checkable classes."""



from dataclasses import dataclass
from datetime import date, datetime, time
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
import tomllib
from typing import Any, Callable, Dict, List, Literal, NoReturn, Sequence, TypeGuard, TypeVar, Union, cast


from .error import FluxCardConfigFieldRequiredError, FluxCardConfigTypeError, FluxCardConfigValueError
from .monads import Box, Maybe
from .output_registry import RegistrationTracker
from .schedules import DaysCycleSchedule, ManualCycleSchedule, MonthCycleSchedule

# Define the allowed scalar types from the TOML specification
TomlScalar = Union[str, int, float, bool, datetime, date, time]

TomlType = Union[
    TomlScalar,
    List["TomlType"],
    Dict[str, "TomlType"]
]

TomlTable = Dict[str, TomlType]
TomlArray = List[TomlType]



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
    raise FluxCardConfigTypeError(f'type error at {key}, expected type {expected_type}, but got type {got_type}{f'\n{more_info}' if more_info else ''}')

def raise_value_error(key: str, value: Any, error: str) -> NoReturn:
    raise FluxCardConfigValueError(f'value error at {key}, expected {error}, but got {value}')

def raise_required_field_error(key: str) -> NoReturn:
    raise FluxCardConfigFieldRequiredError(f'{key} field required')

from typing import Callable, TypeVar, Any

T = TypeVar("T")
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




def resolve_config_relative_path(raw_path: str, config_file: Path) -> Path:
    """
    Normalizes a path string from TOML. 
    Absolute paths stay absolute. Relative paths anchor to the config file's directory.
    """
    p = Path(raw_path).expanduser()
    if p.is_absolute():
        return p
    return (config_file.parent / p).resolve()


class ScheduleConfig:
    raw: TomlTable

    def __init__(self, raw: TomlType):
        if not isinstance(raw,dict):
            raise_type_error('',type(raw).__name__,'dict')
        self.raw = raw

    def get_type(self):
        try:
            return (
                Box(self.raw.get('type'))
                .map(lambda x: x if x is not None else raise_required_field_error('type'))
                .map(lambda x: x if isinstance(x,str) else raise_type_error('type',type(x).__name__,'str'))
                .unwrap()
            )
        except Exception as e:
            e.add_note('key type')
            raise e
     
def parse_days_cycle_from_dict(schedule_config: ScheduleConfig):
    raw = schedule_config.raw
    try:
        anchor = (
            Box(raw.get('period_anchor'))
            .map(lambda x: x if x is not None else raise_required_field_error('period_anchor'))
            .map(lambda x: x if isinstance(x,date) else raise_type_error('days_cycle',type(x).__name__,'date'))
            .unwrap()
        )
    except Exception as e:
        e.add_note('key period_anchor')
        raise e

    try:
        length = (
            Box(raw.get('period_length'))
            .map(lambda x: x if x is not None else raise_required_field_error('period_length'))
            .map(lambda x: x if isinstance(x,int) else raise_type_error('period_length',type(x).__name__,'int'))
            .unwrap()
        )
    except Exception as e:
        e.add_note('key period_length')
        raise e

    return DaysCycleSchedule(anchor,length)

def parse_month_cycle_from_dict(schedule_config: ScheduleConfig) -> MonthCycleSchedule:
    raw = schedule_config.raw
    try:
        start_day = (
            Box(raw.get('start_day'))
            .map(lambda x: x if x is not None else raise_required_field_error('start_day'))
            .map(lambda x: x if isinstance(x,int) else raise_type_error('start_day',type(x).__name__,'int'))
            .map(lambda x: x if (1 <= x <= 28) else raise_value_error('start_day',x,'a value between 1 and 28 inclusive'))
            .unwrap()
        )
    except Exception as e:
        e.add_note('key start_day')
        raise e
        
    return MonthCycleSchedule(start_day)


def parse_manual_cycle(name: str, config: "AppConfig"):
    # have to go pick up the historical markers
    manual_schedule = config.get_manual_schedule(name)
    
    return ManualCycleSchedule(manual_schedule)


class JobConfig:
    raw: TomlTable
    
    def __init__(self, raw: TomlType):
        if not isinstance(raw,dict):
            raise_type_error('',type(raw).__name__,'dict')
        self.raw = raw

    def get_schedule_key(self) -> str | None:

        try:
            return (
                Maybe(self.raw.get('schedule'))
                .map(lambda x: x if isinstance(x,str) else raise_type_error('schedule',type(x).__name__,'str'))
                .unwrap()
            )
        except Exception as e:
            e.add_note('key schedule')
            raise e

class OutputConfig:
    raw: TomlTable
    config_path: Path

    def __init__(self, raw: TomlType, config_path: Path):
        if not isinstance(raw,dict):
            raise_type_error('',type(raw).__name__,'dict')
        self.raw = raw
        self.config_path = config_path

    def get_format(self):
        try:
            return (
                Box(self.raw.get('format'))
                .map(lambda x: x if x is not None else raise_required_field_error('format'))
                .map(lambda x: x if isinstance(x, str) else raise_type_error('format',type(x).__name__,'str'))
                .unwrap()
            )
        except Exception as e:
            e.add_note('key format')
            raise e

    def get_destination(self) -> Path | Literal['stdout']:
        try:
            dest = (Box(self.raw.get('dest','stdout'))
                .map(lambda x: x if isinstance(x, str) else raise_type_error('dest',type(x).__name__,'str'))
                .unwrap()
            )
        except Exception as e:
            e.add_note('key dest')
            raise e

        return dest if dest == 'stdout' else resolve_config_relative_path(dest,self.config_path)

    def get_extra(self):
        args = self.raw.copy()
        args.pop('format')
        if 'dest' in args:
            args.pop('dest')
        return args


class MacroConfig:
    raw: TomlTable
    config_path: Path

    def __init__(self, raw: TomlType, config_path: Path):
        if not isinstance(raw,dict):
            raise_type_error('',type(raw).__name__,'dict')
        self.raw = raw
        self.config_path = config_path
    
    def get_job_filter(self):
        try:
            return (
                Maybe(self.raw.get('job_filter'))
                .map(lambda x: x if isinstance(x,str) or isinstance(x,list) and is_list_strings(x) else raise_type_error('job_filter',type(x).__name__,'str or list of str'))
                .unwrap()
            )
        except Exception as e:
            e.add_note('key job_filter')
            raise e

    def get_period_value(self) -> int | None:
        try:
            return (
                Maybe(self.raw.get('period'))
                .map(lambda x: x if isinstance(x,int) else raise_type_error('period',type(x).__name__,'int'))
                .unwrap()
            )
        except Exception as e:
            e.add_note('key period')
            raise e

    def get_output_configs(self) -> List[OutputConfig]:
        try:
            return (
                Box(self.raw.get('outputs',[]))
                .map(lambda x: x if isinstance(x,list) else raise_type_error('outputs',type(x).__name__,'list'))
                .map(list_for_each(with_key_note(lambda i: f'output {i}',lambda i,x: OutputConfig(x,self.config_path))))
                .unwrap()
            )
        except Exception as e:
            e.add_note('key outputs')
            raise e
    

def load_plugin(path: str, index: int, config_path: Path) -> None:
    file_path = resolve_config_relative_path(path, config_path)

    if not file_path.exists():
        raise FluxCardConfigValueError(f'unknown file path {file_path}')

    # using an index value to make sure that modules are uniquely named
    module_name = f"_dynamic_plugin_{file_path.stem}_{index}"

    tracker = RegistrationTracker()

    tracker.begin()

    try:
        spec = spec_from_file_location(module_name, str(file_path))
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load specifications for: {file_path}")

        module = module_from_spec(spec)
        sys.modules[module_name] = module

        # run the module
        spec.loader.exec_module(module)

    finally:
        # this removes it from sys.modules because we don't need it to be there.
        if module_name in sys.modules:
            del sys.modules[module_name]
    
    added_formatters = tracker.finish()
    if len(added_formatters) > 0:
        added_str = ', '.join(f"'{k}'" for k in sorted(added_formatters))
        print(f'loaded module at {file_path} and added formatter{'s' if len(added_formatters) > 1 else ''} {added_str}')
    else:
        print(f'warning: loaded module at {file_path} but no formatters were registered')






@dataclass(frozen=True)
class AppConfig:
    config_path: Path
    raw: TomlTable

    # output_timezone: ZoneInfo | None # = field(default=None)
    # default_job: str | None # = field(default=None)
    # schedules: Dict[str,Schedule] # = cast(Dict[str, ScheduleConfig],field(default_factory=dict))
    # jobs: Dict[str, JobConfig] # = cast(Dict[str, JobConfig],field(default_factory=dict))
    # macros: Dict[str, MacroConfig] # = cast(Dict[str, MacroConfig], field(default_factory=dict))
    
    def get_output_plugins(self) -> List[Path]:
        try:
            return (
                Maybe(self.raw.get('output_plugins'))
                .map(lambda x: x if isinstance(x,list) else raise_type_error('output_plugins',type(x).__name__,'list'))
                .map(list_for_each(with_key_note(lambda i: f'output plugin {i}',lambda i,x: resolve_config_relative_path(x, self.config_path) if isinstance(x,str) else raise_type_error(f'output_plugins.{i}',type(x).__name__,'str'))))
                .unwrap_or(list)
            )
        except Exception as e:
            e.add_note('key output_plugins')
            raise e

    def get_timecard_path(self) -> Path | None:
        try:
            return (
                Maybe(self.raw.get('timecard_path'))
                .map(lambda x: x if isinstance(x,str) else raise_type_error('timecard_path',type(x).__name__,'str'))
                .map(lambda x: resolve_config_relative_path(x,self.config_path))
                .unwrap()
            )
        except Exception as e:
            e.add_note('key timecard_path')
            raise e

    def get_output_timezone(self):
        try:
            return (
                Maybe(self.raw.get('output_timezone'))
                .map(lambda x: x if isinstance(x,str) else raise_type_error('output_timezone',type(x).__name__,'str'))
                .unwrap()
            )
        except Exception as e:
            e.add_note('key output_timezone')
            raise e

    def get_default_job(self):
        try:
            return (
                Maybe(self.raw.get('default_job'))
                .map(lambda x: x if isinstance(x,str) else raise_type_error('default_job',type(x).__name__,'str'))
                .unwrap()
            )
        except Exception as e:
            e.add_note('key default_job')
            raise e

    def get_schedule(self,schedule_name: str) -> ScheduleConfig | None:
        # step 1, get the schedule table
        try:
            schedules = (
                Maybe(self.raw.get('schedules'))
                .map(lambda x: x if isinstance(x,dict) else raise_type_error('schedules',type(x).__name__,'dict'))
                .unwrap_or(dict)
            )
        except Exception as e:
            e.add_note('table schedules')
            raise e

        # step 2, get the schedule from it
        return (
            Maybe(schedules.get(schedule_name))
            .map(lambda x: ScheduleConfig(x))
            .unwrap()
        )
    

    def get_job_config(self, job_name: str) -> JobConfig | None:
        try:
            jobs = (
                Maybe(self.raw.get('jobs'))
                .map(lambda x: x if isinstance(x,dict) else raise_type_error('jobs',type(x).__name__,'dict'))
                .unwrap_or(dict)
            )
            try:

                return (
                    Maybe(jobs.get(job_name))
                    .map(JobConfig)
                    .unwrap()
                )
            except Exception as e:
                e.add_note(f'key {job_name}')

        except Exception as e:
            e.add_note('table jobs')
            raise e


    def get_macro_config(self, macro: str) -> MacroConfig | None:
        try:
            macros = (
                Maybe(self.raw.get('macros'))
                .map(lambda x: x if isinstance(x,dict) else raise_type_error('macros',type(x).__name__,'dict'))
                .unwrap_or(dict)
            )
            try:
                return (
                    Maybe(macros.get(macro))
                    .map(lambda x: MacroConfig(x, self.config_path))
                    .unwrap()
                )
            except Exception as e:
                e.add_note(f'key {macro}')
                raise e

        except Exception as e:
            e.add_note('table macros')
            raise e


    def get_manual_schedule(self, schedule_name: str) -> List[date]:
        try:
            manual_schedule = (
                Maybe(self.raw.get('manual_schedule_history'))
                .map(lambda x: x if isinstance(x,dict) else raise_type_error('manual_schedule_history',type(x).__name__,'dict'))
                .unwrap_or(dict)
            )
        except Exception as e:
            e.add_note('table manual_schedule_history')
            raise e

        
        return (Maybe(manual_schedule.get(schedule_name))
            .map(lambda x: x if isinstance(x,dict) else raise_type_error('manual_schedule_history.[job_name]',type(x).__name__,'dict'))
            .map(lambda x: x.get('markers',[]))
            .map(lambda x: x if isinstance(x,list) else raise_type_error('markers',type(x).__name__,'list'))
            .map(lambda x: x if is_list_dates(x) else raise_type_error('markers',type(x).__name__,'list of dates'))
            .map(lambda x: x if is_date_list_sorted(x) else raise_value_error('markers',x,'the list to be sorted'))
            .unwrap_or(list)
        )
        


        # try:
        #     manual_schedules = (
        #         Maybe(raw.get('manual_schedule_history'))
        #         .map(lambda x: x if isinstance(x,dict) else raise_type_error('manual_schedule_history',type(x).__name__,'dict'))
        #         .unwrap_or(dict)
        #     )
        # except Exception as e:
        #     e.add_note('table manual_schedule_history')
        #     raise e

        



    @classmethod
    def load(cls, path: Path) -> "AppConfig":
        """Create an AppConfig class given an validated file path.
        raises OSError (normal file open errors) if the file can not be opened for any reason
        raises TomlDecodeError if the file is not Toml format"""
        with path.open("rb") as f:
            raw = cast(TomlTable,tomllib.load(f))

        return cls(path,raw)
