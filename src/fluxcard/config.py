"""This file contains classes that give parse the config dictionary and make nice easily type-checkable classes."""



from dataclasses import dataclass, field
from datetime import date, datetime, time
from pathlib import Path
import tomllib
from typing import Any, Callable, Dict, List, Literal, NoReturn, Sequence, TypeGuard, TypeVar, Union, cast


from .error import FluxCardConfigTypeError, FluxCardConfigValueError, FluxCardFieldRequiredError
from .monads import Box, Maybe
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



def raise_type_error(field_path: str, got_type: str, expected_type: str, more_info: str = '') -> NoReturn:
    """raises a flux card config type error with the expected type, given type, and a more info string if you want"""
    raise FluxCardConfigTypeError(f'expected type {expected_type}, but got type {got_type} at\n{field_path}{f'\n{more_info}' if more_info else ''}')

def raise_value_error(field_path: str, value: Any, error: str) -> NoReturn:
    """raises a flux card config value error with the error string, and the value"""
    raise FluxCardConfigValueError(f'expected {error}, but got {value} at \n{field_path}')

def raise_required_field_error(field_path: str) -> NoReturn:
    """raise a flux card field required error with the path info"""
    raise FluxCardFieldRequiredError(f'field required at\n{field_path}')

from typing import Callable, TypeVar, Any

T = TypeVar("T")


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
    field_path: str

    def __init__(self, raw: TomlType, field_path: str, name: str):
        """raises FluxCardConfigTypeError if raw is not a dictionary"""
        if not isinstance(raw,dict):
            raise_type_error('',type(raw).__name__,'dict')
        self.raw = raw
        self.field_path = field_path + '.' + name


    def get_type(self) -> str:
        """get the type field from the schedule config
        
        raises FluxCardRequiredFieldError if the type is not given
        raises FluxcardConfigTypeError if the type is not a string"""
        
        return (
            Box(self.raw.get('type'))
            .map(lambda x: x if x is not None else raise_required_field_error(f'{self.field_path}.type'))
            .map(lambda x: x if isinstance(x,str) else raise_type_error(f'{self.field_path}.type',type(x).__name__,'str'))
            .unwrap()
        )
        
def parse_days_cycle_from_dict(schedule_config: ScheduleConfig) -> DaysCycleSchedule:
    """parses a schedule config object into a days cycle schedule
    assumes type is days cycle
    period_anchor and period_length are required fields
    
    raises FluxCardRequiredFieldError if the one of the fields is not given
    raises FluxCardConfigTypeError if the types are not correct"""
    raw = schedule_config.raw
    
    anchor = (
        Box(raw.get('period_anchor'))
        .map(lambda x: x if x is not None else raise_required_field_error(f'{schedule_config.field_path}.period_anchor'))
        .map(lambda x: x if isinstance(x,date) else raise_type_error(f'{schedule_config.field_path}.days_cycle',type(x).__name__,'date'))
        .unwrap()
    )

    length = (
        Box(raw.get('period_length'))
        .map(lambda x: x if x is not None else raise_required_field_error(f'{schedule_config.field_path}.period_length'))
        .map(lambda x: x if isinstance(x,int) else raise_type_error(f'{schedule_config.field_path}.period_length',type(x).__name__,'int'))
        .unwrap()
    )
    
    return DaysCycleSchedule(anchor,length)

def parse_month_cycle_from_dict(schedule_config: ScheduleConfig) -> MonthCycleSchedule:
    """parses a schedule config object into a days cycle schedule
    assumes type is month cycle
    start_day is a required field
        
    raises FluxCardRequiredFieldError if the field is not given
    raises FluxCardConfigTypeError if the type is not an int
    raises FluxCardConfigValueError if the value is not between 1 and 28 inclusive"""

    raw = schedule_config.raw
    
    start_day = (
        Box(raw.get('start_day'))
        .map(lambda x: x if x is not None else raise_required_field_error(f'{schedule_config.field_path}.start_day'))
        .map(lambda x: x if isinstance(x,int) else raise_type_error(f'{schedule_config.field_path}.start_day',type(x).__name__,'int'))
        .map(lambda x: x if (1 <= x <= 28) else raise_value_error(f'{schedule_config.field_path}.start_day',x,'a value between 1 and 28 inclusive'))
        .unwrap()
    )
        
    return MonthCycleSchedule(start_day)


def parse_manual_cycle(name: str, config: "AppConfig") -> ManualCycleSchedule:
    """creates a manual cycle schedule object from the markers in config
    
    raises FluxCardConfigTypeError for wrong types in config file
    raises FluxcardConfigValueError for wrong values in config file"""
    # have to go pick up the historical markers
    manual_schedule = config.get_manual_schedule(name)
    
    return ManualCycleSchedule(manual_schedule)


class JobConfig:
    raw: TomlTable
    field_path: str
    
    def __init__(self, raw: TomlType, field_path: str, name: str):
        """raises FluxCardConfigTypeError if raw is not a dictionary"""
        if not isinstance(raw,dict):
            raise_type_error('',type(raw).__name__,'dict')
        self.raw = raw
        self.field_path = field_path + '.' + name

    def get_schedule_key(self) -> str | None:
        """get the schedule name assigned to this job, none if no schedule given
        
        raises FluxCardConfigTypeError if the field is not a string"""

        return (
            Maybe(self.raw.get('schedule'))
            .map(lambda x: x if isinstance(x,str) else raise_type_error(f'{self.field_path}.schedule',type(x).__name__,'str'))
            .unwrap()
        )
        

class OutputConfig:
    raw: TomlTable
    config_path: Path
    field_path: str

    def __init__(self, raw: TomlType, config_path: Path, field_path: str, index: int):
        """raises type error if raw is not a dictionary"""
        if not isinstance(raw,dict):
            raise_type_error('',type(raw).__name__,'dict')
        self.raw = raw
        self.config_path = config_path
        self.field_path = field_path + f'[{index}]'


    def get_format(self):
        """Get the format key from an output
        raises FluxCardRequiredFieldError if the format is not given
        raises FluxCardConfigTypeError if the format is not a string"""
        return (
            Box(self.raw.get('format'))
            .map(lambda x: x if x is not None else raise_required_field_error(f'{self.field_path}.format'))
            .map(lambda x: x if isinstance(x, str) else raise_type_error(f'{self.field_path}.format',type(x).__name__,'str'))
            .unwrap()
        )

    def get_destination(self) -> Path | Literal['stdout']:
        """Get the destination from output, returns stdout if no destination given
        raises FluxCardConfigTypeError if the value is not a string"""
        dest = (Box(self.raw.get('dest','stdout'))
            .map(lambda x: x if isinstance(x, str) else raise_type_error(f'{self.field_path}.dest',type(x).__name__,'str'))
            .unwrap()
        )
        
        return dest if dest == 'stdout' else resolve_config_relative_path(dest,self.config_path)

    def get_extra(self) -> Dict[str,TomlType]:
        """Get any extra keys (other than format and dest) from the output config"""
        args = self.raw.copy()
        args.pop('format')
        if 'dest' in args:
            args.pop('dest')
        return args


class MacroConfig:
    raw: TomlTable
    config_path: Path
    field_path: str

    def __init__(self, raw: TomlType, config_path: Path, field_path: str, name: str):
        """raises FluxCardConfigTypeError if raw is not a dictionary"""
        if not isinstance(raw,dict):
            raise_type_error('',type(raw).__name__,'dict')
        self.raw = raw
        self.config_path = config_path
        self.field_path = field_path + '.' + name
    
    def get_job_filter(self) -> str | List[str] | None:
        """returns a string or list of strings of the macro config job filter, returns the type in the config file
        returns None if the key is not found
        raises FluxCardConfigTypeError if the type is not a list of strings or is a string"""
        return (
            Maybe(self.raw.get('job_filter'))
            .map(lambda x: x if isinstance(x,str) or isinstance(x,list) and is_list_strings(x) else raise_type_error(f'{self.field_path}.job_filter',type(x).__name__,'str or list of str'))
            .unwrap()
        )
        
    def get_period_value(self) -> int | None:
        """returns a integer value for the period offset from the macro config
        returns None if the key is not found
        raises FluxCardConfigTypeError if the type is not an integer"""
        return (
            Maybe(self.raw.get('period'))
            .map(lambda x: x if isinstance(x,int) else raise_type_error(f'{self.field_path}.period',type(x).__name__,'int'))
            .unwrap()
        )

    
    def get_output_configs(self) -> List[OutputConfig]:
        """return a list of output configurations included in this macro
        
        raises FluxCardConfigTypeError if the types of any output config is incorrect
        """
        return (
            Box(self.raw.get('outputs',[]))
            .map(lambda x: x if isinstance(x,list) else raise_type_error(f'{self.field_path}.outputs',type(x).__name__,'list'))
            .map(list_for_each(lambda i,x: OutputConfig(x,self.config_path,f'{self.field_path}.outputs',i)))
            .unwrap()
        )

@dataclass(frozen=True)
class AppConfig:
    config_path: Path
    field_path: str = field(init=False)
    raw: TomlTable

    def __post_init__(self):
        object.__setattr__(self,'field_path',f'{str(self.config_path)}:')


    # output_timezone: ZoneInfo | None # = field(default=None)
    # default_job: str | None # = field(default=None)
    # schedules: Dict[str,Schedule] # = cast(Dict[str, ScheduleConfig],field(default_factory=dict))
    # jobs: Dict[str, JobConfig] # = cast(Dict[str, JobConfig],field(default_factory=dict))
    # macros: Dict[str, MacroConfig] # = cast(Dict[str, MacroConfig], field(default_factory=dict))
    
    def get_output_plugins(self) -> List[Path]:
        """get the resolved path of all output plugins, returns a list of resolved paths
        returns empty list if key is not given
        raises FluxCardConfigTypeError if output_plugins is not a list
        raises FluxCardConfigTypeError if a plugin is not a string"""
    
        return (
            Maybe(self.raw.get('output_plugins'))
            .map(lambda x: x if isinstance(x,list) else raise_type_error(f'{self.field_path}output_plugins',type(x).__name__,'list'))
            .map(list_for_each(lambda i,x: resolve_config_relative_path(x, self.config_path) if isinstance(x,str) else raise_type_error(f'{self.field_path}output_plugins[{i}]',type(x).__name__,'str')))
            .unwrap_or(list)
        )

    def get_timecard_path(self) -> Path | None:
        """get the resolved input path from the config file.
        returns None if key not given.
        raises FluxCardConfigTypeError if the value is not a string"""

        return (
            Maybe(self.raw.get('timecard_path'))
            .map(lambda x: x if isinstance(x,str) else raise_type_error(f'{self.field_path}timecard_path',type(x).__name__,'str'))
            .map(lambda x: resolve_config_relative_path(x,self.config_path))
            .unwrap()
        )


    def get_output_timezone(self) -> str | None:
        """get the timezone string from the config file
        returns None if key is not given.
        raises FluxCardConfigTypeError if the value is not a string"""
        
        return (
            Maybe(self.raw.get('output_timezone'))
            .map(lambda x: x if isinstance(x,str) else raise_type_error(f'{self.field_path}output_timezone',type(x).__name__,'str'))
            .unwrap()
        )
        
    def get_default_job(self) -> str | None:
        """get the default job from the config file
        returns None if key is not given
        raises FluxCardConfigTypeError if the value is not a string"""

        return (
            Maybe(self.raw.get('default_job'))
            .map(lambda x: x if isinstance(x,str) else raise_type_error(f'{self.field_path}default_job',type(x).__name__,'str'))
            .unwrap()
        )
        
    def get_schedule(self,schedule_name: str) -> ScheduleConfig | None:
        """get a schedule config object from the config file
        returns None if the key is not given
        raises FluxCardConfigTypeError if the schedules table is not a dictionary
        raises FluxCardConfigTypeError if the schedule is not a dictionary"""

        # step 1, get the schedule table
        schedules = (
            Maybe(self.raw.get('schedules'))
            .map(lambda x: x if isinstance(x,dict) else raise_type_error(f'{self.field_path}schedules',type(x).__name__,'dict'))
            .unwrap_or(dict)
        )

        # step 2, get the schedule from it
        return (
            Maybe(schedules.get(schedule_name))
            .map(lambda x: ScheduleConfig(x,self.field_path+'schedules',schedule_name))
            .unwrap()
        )
    

    def get_job_config(self, job_name: str) -> JobConfig | None:
        """get a job config object from the config file
        returns None if the key is not given
        raises FluxCardConfigTypeError if the jobs table is not a dictionary
        raises FluxCardConfigTypeError if the job is not a dictionary"""
        jobs = (
            Maybe(self.raw.get('jobs'))
            .map(lambda x: x if isinstance(x,dict) else raise_type_error(f'{self.field_path}jobs',type(x).__name__,'dict'))
            .unwrap_or(dict)
        )

        return (
            Maybe(jobs.get(job_name))
            .map(lambda x: JobConfig(x,f'{self.field_path}jobs',job_name))
            .unwrap()
        )
        

    def get_macro_config(self, macro: str) -> MacroConfig | None:
        """get a macro config object from the config file
        returns None if the key is not given
        raises FluxCardConfigTypeError if the macros table is not a dictionary
        raises FluxCardConfigTypeError if the macro is not a dictionary"""
        
        macros = (
            Maybe(self.raw.get('macros'))
            .map(lambda x: x if isinstance(x,dict) else raise_type_error(f'{self.field_path}macros',type(x).__name__,'dict'))
            .unwrap_or(dict)
        )

        return (
            Maybe(macros.get(macro))
            .map(lambda x: MacroConfig(x, self.config_path,f'{self.field_path}macros',macro))
            .unwrap()
        )

    def get_manual_schedule(self, schedule_name: str) -> List[date]:
        """get a manual schedule entries from the config file, returns a list of sorted dates.
        returns empty list if key is not given (as it could mean no dates have been put in the schedule yet)
        raises FluxCardConfigTypeError if manual_schedule_history table is not a dictionary
        raises FluxCardConfigTypeError if the entry is not of the right form. markers=[dates] dates
        raises FluxCardConfigValueError if the dates in the list are not sorted"""
        
        manual_schedule = (
            Maybe(self.raw.get('manual_schedule_history'))
            .map(lambda x: x if isinstance(x,dict) else raise_type_error('manual_schedule_history',type(x).__name__,'dict'))
            .unwrap_or(dict)
        )
        
        return (Maybe(manual_schedule.get(schedule_name))
            .map(lambda x: x if isinstance(x,dict) else raise_type_error(f'manual_schedule_history.{schedule_name}',type(x).__name__,'dict'))
            .map(lambda x: x.get('markers',[]))
            .map(lambda x: x if isinstance(x,list) else raise_type_error('markers',type(x).__name__,'list'))
            .map(lambda x: x if is_list_dates(x) else raise_type_error('markers',type(x).__name__,'list of dates'))
            .map(lambda x: x if is_date_list_sorted(x) else raise_value_error('markers',x,'the list to be sorted'))
            .unwrap_or(list)
        )

    @classmethod
    def load(cls, path: Path) -> "AppConfig":
        """Create an AppConfig class given an validated file path.
        raises OSError (normal file open errors) if the file can not be opened for any reason
        raises TomlDecodeError if the file is not Toml format"""
        with path.open("rb") as f:
            raw = cast(TomlTable,tomllib.load(f))

        return cls(path,raw)
