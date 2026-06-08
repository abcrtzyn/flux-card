"""This file contains classes that give parse the config dictionary and make nice easily type-checkable classes."""



from dataclasses import dataclass
from datetime import date, datetime, time
from importlib.util import module_from_spec, spec_from_file_location
import inspect
from pathlib import Path
import sys
import tomllib
from typing import Any, Callable, Dict, Iterable, List, NoReturn, Sequence, Set, TypeGuard, TypeVar, Union, cast
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


from .error import FluxCardConfigFieldRequiredError, FluxCardConfigTypeError, FluxCardConfigValueError
from .monads import Box, Maybe
from .output_registry import get_formatter
from .output_runners import FileRunner, OutputRunner, StdoutRunner
from .schedules import DaysCycleSchedule, ManualCycleSchedule, MonthCycleSchedule, Schedule

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


def parse_schedule_from_dict(raw: TomlTable,manual_schedules_raw: TomlType|None) -> Schedule:
    try:
        schedule_type = (
            Box(raw.get('type'))
            .map(lambda x: x if x is not None else raise_required_field_error('type'))
            .map(lambda x: x if isinstance(x,str) else raise_type_error('type',type(x).__name__,'str'))
            .unwrap()
        )
    except Exception as e:
        e.add_note('key type')
        raise e
    
    match schedule_type:
        case 'days_cycle':
            return _parse_days_cycle_from_dict(raw)
        case 'monthly':
            return _parse_month_cycle_from_dict(raw)
        case 'manual':
            return _parse_manual_cycle(raw)
        case _:
            raise FluxCardConfigValueError(f'Unknown schedule type {schedule_type} at key schedule')
    
    assert False, "unreachable"

def _parse_days_cycle_from_dict(raw: TomlTable):
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

def _parse_month_cycle_from_dict(raw: TomlTable) -> MonthCycleSchedule:
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


def _parse_manual_cycle(manual_schedules_raw: TomlType | None):
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
    
    return ManualCycleSchedule(markers)




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
            e.add_note('key schedule')
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
        e.add_note('key format')
        raise e
    # remove the key from the dictionary
    raw.pop('format')
    try:
        dest = Box(raw.get('dest','stdout')).map(lambda x: x if isinstance(x, str) else raise_type_error('dest',type(x).__name__,'str')).unwrap()
    except Exception as e:
        e.add_note('key dest')
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
            raise FluxCardConfigValueError(f'Format "{form}" received unsupported options: {', '.join(invalid_keys)}')
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
            e.add_note('key job_filter')
            raise e

        try:
            period = (
                Maybe(raw.get('period'))
                .map(lambda x: x if isinstance(x,int) else raise_type_error('period',type(x).__name__,'int'))
                .unwrap()
            )
        except Exception as e:
            e.add_note('key period')
            raise e

        try:
            outputs = (
                Box(raw.get('outputs',[]))
                .map(lambda x: x if isinstance(x,list) else raise_type_error('outputs',type(x).__name__,'list'))
                .map(list_for_each(with_key_note(lambda i: f'output {i}',lambda i,x: parse_output_runner_from_dict(x,config_path) if isinstance(x,dict) else raise_type_error(f'outputs.{i}',type(x).__name__,'dict'))))
                .unwrap()
            )
        except Exception as e:
            e.add_note('key outputs')
            raise e

        return cls(job_filter,period,outputs)
    

def load_plugin(path: str, index: int, config_path: Path) -> None:
    file_path = resolve_config_relative_path(path, config_path)

    if not file_path.exists():
        raise FluxCardConfigValueError(f'unknown file path {file_path}')

    # using an index value to make sure that modules are uniquely named
    module_name = f"_dynamic_plugin_{file_path.stem}_{index}"

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




@dataclass(frozen=True)
class AppConfig:
    timecard_path: Path | None # = field(default=None)
    output_timezone: ZoneInfo | None # = field(default=None)
    default_job: str | None # = field(default=None)
    schedules: Dict[str,Schedule] # = cast(Dict[str, ScheduleConfig],field(default_factory=dict))
    jobs: Dict[str, JobConfig] # = cast(Dict[str, JobConfig],field(default_factory=dict))
    macros: Dict[str, MacroConfig] # = cast(Dict[str, MacroConfig], field(default_factory=dict))
    
    @classmethod
    def from_dict(cls, raw: TomlTable, config_path: Path) -> "AppConfig":
        
        # step one, load the plugins
        try:
            (
                Maybe(raw.get('output_plugins'))
                .map(lambda x: x if isinstance(x,list) else raise_type_error('output_plugins',type(x).__name__,'list'))
                .map(list_for_each(with_key_note(lambda i: f'output plugin {i}',lambda i,x: load_plugin(x,i,config_path) if isinstance(x,str) else raise_type_error(f'output_plugins.{i}',type(x).__name__,'str'))))
                .unwrap()
            )
        except Exception as e:
            e.add_note('key output_plugins')
            raise e

        # step two, do everything else

        try:
            timecard_path = (
                Maybe(raw.get('timecard_path'))
                .map(lambda x: x if isinstance(x,str) else raise_type_error('timecard_path',type(x).__name__,'str'))
                .map(lambda x: resolve_config_relative_path(x,config_path))
                .unwrap()
            )
        except Exception as e:
            e.add_note('key timecard_path')
            raise e

        try:
            output_timezone = (
                Maybe(raw.get('output_timezone'))
                .map(lambda x: x if isinstance(x,str) else raise_type_error('output_timezone',type(x).__name__,'str'))
                .map(ZoneInfo)
                .unwrap()
            )
        except (ValueError, ZoneInfoNotFoundError) as e:
            e.add_note('key output_timezone')
            raise FluxCardConfigValueError(e)
            
        except Exception as e:
            e.add_note('key output_timezone')
            raise e

        try:
            default_job = (
                Maybe(raw.get('default_job'))
                .map(lambda x: x if isinstance(x,str) else raise_type_error('default_job',type(x).__name__,'str'))
                .unwrap()
            )
        except Exception as e:
            e.add_note('key default_job')
            raise e

        try:
            manual_schedules = (
                Maybe(raw.get('manual_schedule_history'))
                .map(lambda x: x if isinstance(x,dict) else raise_type_error('manual_schedule_history',type(x).__name__,'dict'))
                .unwrap_or(dict)
            )
        except Exception as e:
            e.add_note('table manual_schedule_history')
            raise e

        try:
            schedules = (
                Maybe(raw.get('schedules'))
                .map(lambda x: x if isinstance(x,dict) else raise_type_error('schedules',type(x).__name__,'dict'))
                .map(dict_for_each(with_key_note(lambda k: f'schedule {k}',lambda k,v: (parse_schedule_from_dict(v,manual_schedules.get(k)) if isinstance(v,dict) else raise_type_error(f'schedules.{k}',type(v).__name__,'dict')))))
                .unwrap_or(dict)
            )
        except Exception as e:
            e.add_note('table schedules')
            raise e
        
        schedule_keys = schedules.keys()

        try:
            jobs = (
                Maybe(raw.get('jobs'))
                .map(lambda x: x if isinstance(x,dict) else raise_type_error('jobs',type(x).__name__,'dict'))
                .map(dict_for_each(with_key_note(lambda k: f'job {k}',lambda k,v: (JobConfig.from_dict(v,schedule_keys) if isinstance(v,dict) else raise_type_error(f'jobs.{k}',type(v).__name__,'dict')))))
                .unwrap_or(dict)
            )
        except Exception as e:
            e.add_note('table jobs')
            raise e

        try:
            macros = (
                Maybe(raw.get('macros'))
                .map(lambda x: x if isinstance(x,dict) else raise_type_error('macros',type(x).__name__,'dict'))
                .map(dict_for_each(with_key_note(lambda k: f'macro {k}',lambda k,v: (MacroConfig.from_dict(v,config_path) if isinstance(v,dict) else raise_type_error(f'macros.{k}',type(v).__name__,'dict')))))
                .unwrap_or(dict)
            )
        except Exception as e:
            e.add_note('table macros')
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
        try:
            return cls.from_dict(raw, path)
        except Exception as e:
            e.add_note(f'File {str(path)}')
            raise e
        
        assert False, 'unreachable'

    def job_config(self, job_name: str | None) -> JobConfig:
        if job_name is None:
            return JobConfig(None)
        # if the job is not listed in the config, return a blank one as well
        return self.jobs.get(job_name, JobConfig(None))
