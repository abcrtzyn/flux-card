#!/usr/bin/env python3


# this loads all the output formats into the registry
import argparse
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from enum import Enum, auto
from importlib.util import module_from_spec, spec_from_file_location
import inspect
import logging
import os
from pathlib import Path
import re
import sys
from tomllib import TOMLDecodeError
from typing import Any, Dict, Iterable, Iterator, List, Literal, Set, Tuple, overload
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fluxcard.config import AppConfig, MacroConfig, OutputConfig, ScheduleConfig, TomlTable, parse_days_cycle_from_dict, parse_manual_cycle, parse_month_cycle_from_dict
from fluxcard.error import FluxCardCommandLineError, FluxCardConfigValueError, FluxCardError, FluxCardFieldRequiredError, FluxCardInputError, FluxCardPluginError, print_terminal_error
from fluxcard.output_registry import RegistrationTracker, get_formatter, print_formatters
from fluxcard.output_runners import FileRunner, OutputRunner, StdoutRunner
from fluxcard.schedules import Schedule
from fluxcard.segments import Segment
from fluxcard.settings_parsers import OutputSettingsAction

# this loads all the output formats into the registry
from . import outputs  # pyright: ignore[reportUnusedImport]

PROGRAM_FORMAT_PARAMS = {'filter_start_date', 'filter_end_date'}


class DateFilterMode(Enum):
    CLI_DATE = auto()
    PERIOD = auto()
    NONE = auto()

# this goes in the rest of the files
logger = logging.getLogger(__name__)

def setup_logging(verbosity_score: int):
    """Initializes global logging to print cleanly to the terminal screen."""

    if verbosity_score == 0:
        target_level = logging.ERROR  # Silent default
    elif verbosity_score == 1:
        target_level = logging.WARNING  # -v
    elif verbosity_score == 2:
        target_level = logging.INFO  # -vv
    else:
        target_level = logging.DEBUG  # -vvv or higher

    # Define a clean layout for developers reading logs
    log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    
    logging.basicConfig(
        level=target_level,
        format=log_format,
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout                  # Send standard logs to stdout
    )


class FluxCardArgumentParser(argparse.ArgumentParser):
    """Subclass to change the error type to Fluxcard Error"""

    def error(self, message: str):
        raise FluxCardCommandLineError(f"{message}")

@dataclass
class ParsedArgs:
    alt_config: Path | None
    timecard_path: Path | None
    output_timezone: str | None
    job_filter: str | None
    start_date: date | None
    end_date: date | None
    period: int | None
    output: Tuple[str,str] | None
    macro: str | None
    print_config: bool
    list_formats: bool
    verbose: int



def parse_args() -> ParsedArgs:
    """Parse command line arguments using ArgumentParser
    raises FluxCardCommandLineError"""

    parser = FluxCardArgumentParser(prog="fluxcard",description="Summarize clock in sessions from the input file.\nUses settings from command line and config.toml")

    parser.add_argument("-c","--config",dest="alt_config", type=lambda x: Path(x).expanduser().resolve() if x else None, help="Alternate config file path")

    parser.add_argument("-i", "--input", dest="timecard_path", type=lambda x: Path(x).expanduser().resolve() if x else None, help="Path to input file")
    parser.add_argument("-tz", "--timezone", type=str, dest="output_timezone", help="timezone to format output")
    
    parser.add_argument("-j","--job",dest="job_filter",type=str, help='Job(s) to filter by seperated by comma "WebDev,Gardening". Clear filter set by config with "_". One job is required in period mode')


    parser.add_argument("start_date", nargs="?", type=parse_cli_start_date, help="Optinal start date, can use _ as a placeholder (YYYY-MM-DD)")
    parser.add_argument("end_date", nargs="?", type=parse_cli_end_date, help="Optinal end date, not including the day itself (YYYY-MM-DD)")

    parser.add_argument("-p", "--period", type=int, help="Period index (0=current, 1=previous, etc.), replaces date filtering mode")
    parser.add_argument("-o", "--output",nargs=2,action=OutputSettingsAction, metavar=("DESTINATION","FORMAT"), help="where and what to output. Destination can be 'stdout' or a file path (absolute or cwd relative), format can be any string that is has an output function.")

    parser.add_argument('-m', "--macro", type=str, help="Macro to run, macros can be set in the config file to run commands with job filters and multiple output formats")
    parser.add_argument("--print-config",action="store_true", help="Print resolved configuration and exit")
    parser.add_argument("--list-formats",action="store_true", help="Print the list of formatter functions and exit")

    parser.add_argument("-v","--verbose",action="count",default=0,help="Increase logging output verbosity: -v (warn), -vv (info), -vvv (debug).")

    raw_args = parser.parse_args()

    return ParsedArgs(
        alt_config=raw_args.alt_config,
        timecard_path=raw_args.timecard_path,
        output_timezone=raw_args.output_timezone,
        job_filter=raw_args.job_filter,
        start_date=raw_args.start_date,
        end_date=raw_args.end_date,
        period=raw_args.period,
        output=raw_args.output,
        macro=raw_args.macro,
        print_config=raw_args.print_config,
        list_formats=raw_args.list_formats,
        verbose=raw_args.verbose
    )


def parse_cli_start_date(date_str: str|None):
    """Parse the start date from isoformat or '_'. raises ArgumentTypeError (used by argparse)"""
    if date_str is None or date_str in ("_", ""):
        return None
    try:
        return date.fromisoformat(date_str)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid value '{date_str}', valid dates are 'YYYY-MM-DD' or '_'.")

def parse_cli_end_date(date_str: str|None):
    """Parse the end date from isoformat. raises ArugmentTypeError (used by argparse)"""
    if date_str is None or date_str in (""):
        return None
    try:
        return date.fromisoformat(date_str)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid value '{date_str}', valid dates are 'YYYY-MM-DD'")

@overload
def _check_and_load(path: Path, is_explicit: Literal[True]) -> AppConfig: ...

@overload
def _check_and_load(path: Path, is_explicit: Literal[False]) -> AppConfig | None: ...

def _check_and_load(path: Path, is_explicit: bool) -> AppConfig | None:
    """Load the config at path. 
    If is_explicit is True, will return AppConfig or raise an FluxCardInputError if the file can not be read
    If is_explicit is False, will return AppConfig or return None if the file can not be read
    
    In either case, can raise TOMLDecodeError if the decoding is not successful"""

    try:
        if path.is_dir():
            raise IsADirectoryError("Target path is a directory, not a file.")
        data = AppConfig.load(path)
        logger.info(f"File handle opened and parsed: '{path}'")
        return data
    except OSError as e:
        # Catches FileNotFoundError, PermissionError, IsADirectoryError, etc.
        if is_explicit:
            raise FluxCardInputError(
                f'Cannot read config file at "{path}": {e.strerror}'
            )
        logger.debug(f"Implicit file skipped. OS message: {e.strerror}")
        return None


def get_config(args: ParsedArgs) -> AppConfig | None:
    """Returns an AppConfig object or None.
    Checks for alt_config option on command line, will raise FluxCardInputError if that file is not readable
    Otherwise uses config.toml in the current working directory, returns None if that file is not readable
    raises FluxCardInputError if the file is not a valid TOML format"""

    config_path = Path.cwd() / "config.toml"
    try:
        # check for alternate config parameter
        if args.alt_config is not None:
            config_path = args.alt_config.resolve()
            logger.debug(f"Alternate configuration file path requested: '{config_path}'")
            # load or raise error
            config = _check_and_load(config_path,True)
            logger.info(f"Successfully loaded alternate configuration file: '{config_path}'")
            return config
        # else, using the normal config path
        logger.debug(f"No alternate config provided. Checking standard path: '{config_path}'")
        # load or return None
        config = _check_and_load(config_path,False)
        if config is None:
            logger.info("No configuration file found at alternate or standard locations. Proceeding with no configuration.")
        else:
            logger.info(f"Successfully loaded default configuration file: '{config_path}'")
        return config
    
    except TOMLDecodeError as e:
        # Could not decode the file as a TOML, this whole section is refactoring the error

        # Extract line and column numbers
        line = getattr(e, "lineno", None)
        col = getattr(e, "colno", None)

        if line is None or col is None:
            match = re.search(r"\(at line (\d+), column (\d+)\)", str(e))
            if match:
                line, col = match.group(1), match.group(2)
        
        clickable_location = f'File "{config_path}", line {line}, col {col}'
        error_msg = getattr(e, "msg", str(e)).split(" (at line")[0]

        raise FluxCardInputError(
            f"Could not decode the configuration file.\n"
            f"  {clickable_location}\n"
            f"  Decode Error: {error_msg}"
        )

    assert False, 'unreachable'

def load_plugin(file_path: Path, index: int) -> None:
    """Load the plugin at the file path, index should be a unique number to differentiate the plugin from others of the same name.
    raises FluxCardPluginError if the module could not be loaded because it is not a valid python file
    raises any errors passed from the module itself
    """

    if not file_path.is_file():
        raise FluxCardPluginError(f"{file_path} is not a file")

    # using an index value to make sure that modules are uniquely named
    module_name = f"_dynamic_plugin_{file_path.stem}_{index}"

    logger.debug(f'loading module at {file_path} as {module_name}')

    # start the registration tracker
    tracker = RegistrationTracker()
    tracker.begin()

    try:
        spec = spec_from_file_location(module_name, str(file_path))
        if spec is None or spec.loader is None:
            raise FluxCardPluginError(f"Could not parse python module spec for {file_path}, is it a python file?")

        module = module_from_spec(spec)
        sys.modules[module_name] = module

        try:
            # run the module
            spec.loader.exec_module(module)
        except Exception:
            # letting all exceptions pass through until I figure out something better to do
            raise
    finally:
        # this removes it from sys.modules because we don't need it to be there.
        if module_name in sys.modules:
            del sys.modules[module_name]
    
    added_formatters = tracker.finish()
    if len(added_formatters) > 0:
        added_str = ', '.join(f"'{k}'" for k in sorted(added_formatters))
        logger.info(f'loaded module at {file_path} and added formatter{'s' if len(added_formatters) > 1 else ''}: {added_str}')
    else:
        logger.warning(f'loaded module at {file_path} but no formatters were registered, check that you have used the @register_formatter decorator')



def get_input_path(args: ParsedArgs, config: AppConfig | None) -> Path:
    """Get the input path from either the config file or the command line args.
    raises FluxCardFieldRequiredError if the input is not specified
    raises FluxCardInputError if the input file is not a file
    raises FluxCardConfigTypeError if the path in the config is not a string"""
    # get the input path from either command line args or config
    # these paths are already abs. paths
    if args.timecard_path is not None:
        input_path = args.timecard_path
        logger.info(f"input path given by command line: {input_path}")
    else:
        input_path = config.get_timecard_path() if config is not None else None
        if input_path is not None:
            logger.info(f"input path given by config: {input_path}")
        
    # check if the path is given, and if we can read from it.
    if input_path is None:
        raise FluxCardFieldRequiredError('"timecard_path" must be specified in config or given as a command line argument -i')
    if not input_path.is_file():
        raise FluxCardInputError(f"The path {input_path} is not a valid file")
    # good enough for now.
    return input_path

def get_output_timezone(args: ParsedArgs, config: AppConfig | None) -> ZoneInfo:
    """Get timezone information from the conmmand line or config
    raises FluxCardFieldRequiredError if the timezone is not specified
    raises FluxCardConfigTypeError if the timezone in the config is not a string
    raises FluxCardInputError if the timezone is not a valid timezone"""

    if args.output_timezone is not None:
        tz_str = args.output_timezone
        logger.info(f'output timezone specified by command line: {tz_str}')
    else:
        tz_str = config.get_output_timezone() if config is not None else None
        if tz_str is not None:
            logger.info(f'output timezone specified by config: {tz_str}')
        
    if tz_str is None:
        raise FluxCardFieldRequiredError('"output_timezone" must be specified in config or given as a command line argument -tz')

    try:
        return ZoneInfo(tz_str)
    except ZoneInfoNotFoundError:
        raise FluxCardInputError(f"time zone '{tz_str}' is unknown")


def get_macro_config(args: ParsedArgs, config: AppConfig | None) -> MacroConfig | None:
    """get the macro config of the macro specified in the command line arguments
    retunrs MacroConfig for the macro specified
    returns None if no macro is specified in the command line arguments
    raises FluxCardConfigTypeError if the config file has bad typing
    raises FluxCardInputError if the macro is not found in the config file"""

    if args.macro is None:
        logger.debug("No macro given in command line args")
        return None

    logger.debug(f"Checking for macro {args.macro} in the config")
    mc = config.get_macro_config(args.macro) if config is not None else None
    if mc is None:
        raise FluxCardInputError(f"'{args.macro}' is not a defined macro\ncheck your spelling, or check that it is actually defined in your config file")

    logger.info(f"Macro config found for macro {args.macro}")
    return mc
    

def get_job_filter(args: ParsedArgs, macro_config: MacroConfig | None, config: AppConfig | None) -> Set[str] | None:
    """Get the job filter specified by command line args, macro config, or default job
    returns a set of jobs for a filter, or None for no filter (all)
    raises FluxCardInputError if the value given is not allowed
    raises FluxCardConfigTypeError if the type in the config is wrong
    
    """
    
    # if the command line arguments have a value, it is always taken
    if args.job_filter is not None:
        # command line arguments can be a single underscore
        logger.debug(f'command line job filter given as "{args.job_filter}"')

        if args.job_filter == '_':
            logger.info(f'job filter is set as no filter')
            return None
        
        # else
        # Split comma-separated inputs and strip whitespace
        job_set = {item.strip() for item in args.job_filter.split(",") if item.strip()}
        if '' in job_set:
            raise FluxCardInputError('found empty string in job filter command line option, please check your')
        if '_' in job_set:
            raise FluxCardInputError("Underscore found in the job filter list, this is undefined behaviour")
        logger.info(f'job filter is set as {job_set}')
        return job_set

    logger.debug('command line job filter is not given')

    # check the macro config
    if macro_config is not None:
        jf = macro_config.get_job_filter()

        logger.debug(f'macro config job filter given as {jf}')

        if isinstance(jf,str):
            if ',' in jf:
                logger.warning('job filter in macro config should be a list of strings, not a comma seperated string')
            if jf == '_':
                raise FluxCardInputError('underscore not allowed in macro config job filter')
            logger.info(f'job filter is set as {{{jf}}}')
            return {jf}
        elif isinstance(jf,list):
            sjf = set(jf)
            if '_' in sjf:
                raise FluxCardInputError('underscore not allowed in macro config job filter')
            logger.info(f'job filter is set as {sjf}')
            return sjf

    logger.debug('no macro config to use job filter')

    # check default job
    if config is not None:
        if dj := config.get_default_job():
            logger.debug(f'default job filter given as {dj}')
            # its not none or ''
            if dj == '_':
                raise FluxCardInputError('underscore not allowed in default job')
            if ',' in dj:
                raise FluxCardInputError('Default job does not take a comma seperated list')
            logger.debug(f'job filter set as {{{dj}}}')
            return {dj}

    logger.debug('no default job in config, job filter set as no filter')
    return None

def get_cli_date_filter(args: ParsedArgs) -> Tuple[date|None,date|None]:
    """get the date filter arguments from the command line args. returns (start_date, end_date)
    raises FluxCardInputError if the start date is after or on the same date as the end date"""

    # date filtering, straight use them
    if args.start_date is not None and args.end_date is not None and args.start_date >= args.end_date:
        raise FluxCardInputError('start date is after or the same as end date, no results would show')
    return (args.start_date, args.end_date)


def get_period_parameter(args: ParsedArgs, macro_config: MacroConfig | None) -> int | None:
    """get the period parameter from the command line args or macro config, None if no value set
    raises FluxCardConfigTypeError if the value in macro config is not an integer"""

    if args.period is not None:
        logger.debug(f'period given in command line arguments, value {args.period}')
        return args.period
    if macro_config is not None:
        value = macro_config.get_period_value()
        if value is not None:
            logger.debug(f'period given in macro config, value {value}')
            return value

    logger.debug(f'no period given')
    
    return None

def create_schedule_from_config(schedule_config: ScheduleConfig, name: str, config: "AppConfig") -> Schedule:
    schedule_type = schedule_config.get_type()

    match schedule_type:
        case 'days_cycle':
            return parse_days_cycle_from_dict(schedule_config)
        case 'monthly':
            return parse_month_cycle_from_dict(schedule_config)
        case 'manual':
            return parse_manual_cycle(name, config)
        case _:
            raise FluxCardConfigValueError(f'Unknown schedule type {schedule_type} at key schedule')
    
    assert False, "unreachable"


def get_schedule(job_filter: Set[str] | None, config: AppConfig | None) -> Schedule:
    if job_filter is None:
        raise FluxCardInputError('job filter is required in period mode and each of the jobs schedules must match')
    if config is None:
        raise FluxCardInputError('config file not given, required for job config and schedule config')

    # check that every job in job_filter has the same schedule set
    schedules: set[str | None] = set()
    for x in job_filter:
        jc = config.get_job_config(x)
        if jc is None:
            raise FluxCardInputError(f"in period mode, every job in job filter must have a job config with a schedule set, job config for '{x} was not found")
        schedules.add(jc.get_schedule_key())

    if len(schedules) != 1:
        raise FluxCardInputError(f'in period mode, every job in job filter must have the same schedule, actually have {schedules}')
    schedule_key = schedules.pop()
    if schedule_key is None:
        raise FluxCardInputError('in period mode, the job(s) filtered by must have a schedule')
    schedule_config = config.get_schedule(schedule_key)
    if schedule_config is None:
        raise FluxCardInputError(f"could not find schedule '{schedule_key}' in the config")

    return create_schedule_from_config(schedule_config,schedule_key,config)

def create_output_runner_common(dest: Path | Literal['stdout'], form: str, extra_kwargs: TomlTable) -> OutputRunner:
    # get the formatter
    try:
        formatter = get_formatter(form)
    except KeyError as e:
        raise FluxCardInputError(e.args[0]) from e

    config_given_params = set(extra_kwargs.keys())
    program_invalid_keys = config_given_params.intersection(PROGRAM_FORMAT_PARAMS)
    if program_invalid_keys:
        raise FluxCardConfigValueError(f'For format "{form}", recieved options that are generated by the program and are not allowed by config: {', '.join(program_invalid_keys)}')

    # check the signature
    sig = inspect.signature(formatter)
    # if the signature has **kwargs in it, we don't check keys.
    if not any(p.kind == p.VAR_KEYWORD for p in sig.parameters.values()):
        wanted_params = set(sig.parameters.keys())
        program_params_requested = wanted_params.intersection(PROGRAM_FORMAT_PARAMS)
        # check for given keys not supported by the formatter
        invalid_keys = config_given_params - wanted_params
        if invalid_keys:
            raise FluxCardConfigValueError(f'Format "{form}" received unsupported options: {', '.join(invalid_keys)}')
        # check for keys that will be defined by the program and thus should not be given by config
    else:
        # **kwards
        # we request all the params we have
        program_params_requested = PROGRAM_FORMAT_PARAMS

    # we have passed the key check here

    # destination can be None or stdout for stdout
    if dest == "stdout":
        return StdoutRunner(form,formatter,extra_kwargs,program_params_requested)
    
    return FileRunner(form,formatter,extra_kwargs,program_params_requested,dest)



def create_output_runner_from_args(output_args: Tuple[str,str]) -> OutputRunner:
    dest = output_args[0]
    # normalizing destination variable, probably don't have to do about half of of the path resolution stuff, but doing it anyway.
    if dest != 'stdout':
        dest = Path(dest).expanduser().resolve()

    return create_output_runner_common(dest,output_args[1],{})

def create_output_runner_from_config(output_config: OutputConfig) -> OutputRunner:
    # output is required, otherwise, how would we know how to output?
    form = output_config.get_format()
    # remove the key from the dictionary
    dest = output_config.get_destination()
    # give these argument versions for actual parsing, along with the rest of the arguments as is.
    return create_output_runner_common(dest,form,output_config.get_extra())




def get_outputs(args: ParsedArgs, macro_config: MacroConfig | None) -> List[OutputRunner]:
    # if args.outputs, then we use the single output definde there
    if args.output is not None:
        return [create_output_runner_from_args(args.output)]

    # else, look at macro config, this can be a list
    if macro_config is not None:
        return [create_output_runner_from_config(x) for x in macro_config.get_output_configs()]

    return []

def check_file_terminator(input_path: Path) -> None:
    """This function checks that the file terminates as expected which must be "\\n=="
    there should be no newline at the end of the file (for now).

    raises FluxCardInputError if the file does not end properly.
    raises OSError if the file could not be opened."""
    try:
        with open(input_path,"rb") as f:
            try:
                f.seek(-3,os.SEEK_END)
                terminator = f.read(3).decode()
                if terminator != '\n==':
                    raise FluxCardInputError("The file does not end with a douple equals, are you still clocked in? Or does the file end with a newline?")
            except OSError:
                # less than three bytes.
                # expecting the first line with '==' and that is it
                f.seek(0)
                text = f.read().decode()
                if text != '==':
                    raise FluxCardInputError("The file does not end with a douple equals, does the file end with a newline?")
    except OSError as e:
        # file could not be opened for some reason
        # for now I'm just going to pass this error on
        raise e
    


def read_segment_lines(input_path: Path) -> Iterator[Tuple[Tuple[Path, int], List[str]]]:
    """Yields each block between lines with ==
    Note that this is very sensitive to lines, if the split line isn't exactly ==, it won't split it
    
    raises FluxCardInputEror if the file does not start the first line with =="""


    with open(input_path) as f:
        # check for a seperator at the top of the file
        line = f.readline().strip()
        if line != '==':
            raise FluxCardInputError('timecard must start with an "==" line',f"Invalid line 1: {line}")
        
        segment_start = 2
        segment_lines: List[str] = []
        # read the rest of the file
        # the lines iterator then starts on the next line
        for line_num, line in enumerate(f,start=2):
            line = line.strip()
            if line == "==":
                yield (input_path, segment_start), segment_lines
                segment_lines = []
                segment_start = line_num + 1
            else:
                segment_lines.append(line)


def parse_timestamp_line(line: str, loc_info: Tuple[Path,int],prefix:str) -> datetime:
    """read a timestamp line, of the form
    {prefix}{iso datetime}

    raise ValueError if the line could not parsed
    """

    if not line.startswith(prefix):
        raise ValueError(f"Parsing Error. {loc_info[0]}:{loc_info[1]} in time line must begin with a '{prefix}' character")
    try:
        return datetime.fromisoformat(line[len(prefix):])
    except ValueError as e:
        e.add_note(f"occured at {loc_info[0]}:{loc_info[1]}")
        raise e

def parse_timecard_segment(lines: List[str], loc_info: Tuple[Path,int], tz: ZoneInfo) -> Segment:
    """read a timecard segment all lines starting from == to the next ==.
    returns a Segment object
    
    raises ValueError if there was a parsing error"""

    if len(lines) == 0:
            raise ValueError(f"Parsing Error. {loc_info[0]}:{loc_info[1]} empty record marked by consectutive == lines")
    if len(lines) < 4:
        raise ValueError(f"Parsing Error. {loc_info[0]}:{loc_info[1]} not enough lines in this record, expecting lines job, intime, outtime, at least one description line (can be empty)")

    job = lines[0]
    in_line = lines[1]
    out_line = lines[2]
    description = "\n".join(lines[3:])
    local_in = parse_timestamp_line(in_line,(loc_info[0],loc_info[1]+1),'>').astimezone(tz)
    local_out = parse_timestamp_line(out_line,(loc_info[0],loc_info[1]+2),'<').astimezone(tz)
    
    return Segment(job,local_in,local_out,description)


def split_across_midnight(segment: Segment, tz: ZoneInfo) -> Iterator[Segment]:
    """take a segment and split it across midnight in the output timezone, yields each split segment as a seperate segment"""

    current_start = segment.inTime
        
    # deal with in-outs that pass on multiple days
    while segment.outTime.date() > current_start.date():
        # Create a midnight marker at 23:59:59.99 for the current day
        current = current_start
        end_of_day = current.replace(hour=23, minute=59, second=59)
        
        yield Segment(segment.job,current_start,end_of_day,segment.description)
        
        # Set the start of the next segment to 00:00:00 of the following day
        next_day = current.date() + timedelta(days=1)
        current_start = datetime.combine(next_day, time.min, tzinfo=tz)
    
    yield Segment(segment.job, current_start, segment.outTime, segment.description)


def parse_segments(segments: Iterable[Tuple[Tuple[Path,int],List[str]]],output_timezone: ZoneInfo) -> Iterator[Segment]:
    """For each unpparsed segment, yield a parsed segment
    
    raises ValueError if the segment can not be parsed"""

    for loc_info, lines in segments:
        segment = parse_timecard_segment(lines,loc_info,output_timezone)
        yield from split_across_midnight(segment,output_timezone)

def job_filter_segments(segments: Iterable[Segment],job: Set[str] | None) -> Iterator[Segment]:
    """Given an iterable of segments, return an iterator of segments filtered only by the job filter set
    If job is None, all segments returned"""

    if job is None:
        return iter(segments)
    
    return (s for s in segments if s.job in job)

def date_filter_segments(segments: Iterable[Segment],start_date: date | None, end_date: date | None) -> Iterator[Segment]:
    """given an iterable of segments, return an iterator of segments filtered by the start and end date.
    return only the segments that match the job filter"""
    if start_date is None and end_date is None:
        yield from segments
    
    for s in segments:
        dat = s.inTime.date()
        if (start_date is None or start_date <= dat) and (end_date is None or dat < end_date):
            yield s


def sort_by_time(segments: Iterable[Segment]) -> List[Segment]:
    """sorts an iterable of segments by the the 'in time' field and returns as a list"""
    return sorted(segments,key=lambda x: x.inTime)


def main():
    try:
        args = parse_args()

        setup_logging(args.verbose)

        config = get_config(args)

        if config is not None:
            plugins = config.get_output_plugins()
            for i,p in enumerate(plugins):
                load_plugin(p,i)
        
        if args.list_formats:
            print_formatters()
            return
        
        input_path = get_input_path(args, config)
        output_timezone = get_output_timezone(args, config)
        macro_config = get_macro_config(args,config)
        job_filter = get_job_filter(args, macro_config, config)

        if args.period is not None and (args.start_date or args.end_date):
            raise FluxCardInputError("Cannot use --period while also using date filter")

        if args.start_date or args.end_date:
            # cli date filter
            start_date, end_date = get_cli_date_filter(args)
        else:
            # check for period input
            period = get_period_parameter(args,macro_config)
            if period is None:
                # no filter
                start_date, end_date = None,None
            else:
                # period filter
                schedule = get_schedule(job_filter,config)
                start_date, end_date = schedule.get_date_filter(period)

        
        outputs = get_outputs(args, macro_config)

        if len(outputs) == 0:
            raise FluxCardInputError('No outputs given, either specify through -o dest format or through -m macro that is defined in your config')


    except FluxCardError as e:
        print_terminal_error(e)
        exit(1)
        
    if args.print_config:
        print('using the following settings')
        print('input file:', input_path)
        print('output timezone:', output_timezone)
        print('job:', job_filter)
        print('start date:', start_date)
        print('end date:', end_date)
        print('outputs:')
        for o in outputs:
            kwargs_str = f" with {o.kwargs}" if o.kwargs else ""
            print(f"  {o.format_key} at {o.output_str()}{kwargs_str}")
            
        return

    check_file_terminator(input_path)
    # file ends properly, lets read some segments
    splits = read_segment_lines(input_path)
    segments = date_filter_segments(job_filter_segments(parse_segments(splits,output_timezone),job_filter),start_date,end_date)
    data = sort_by_time(segments)

    params: Dict[str,Any] = {"filter_start_date": start_date, "filter_end_date": end_date}

    # for compile time, check that params has the same keys as PROGRAM_FORAMT_PARAMS or whotave it is.
    if params.keys() != PROGRAM_FORMAT_PARAMS:
        raise Exception('The program gnerated params for formaters does not match the compile time parameter list, if you added a parameter to one but not the other, please fix that before running again.')

    for o in outputs:
        o.execute_output(data,params)
    


if __name__ == "__main__":
    main()
