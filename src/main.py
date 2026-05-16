#!/usr/bin/env python3

import argparse
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, time, timedelta, date # pyright: ignore[reportPrivateUsage]
from math import floor
import os
from pathlib import Path
import sys
from typing import Iterator, List, Dict, Set, Tuple
from zoneinfo import ZoneInfo

from config import AppConfig, MacroConfig, OutputConfig
from error import FluxCardInputError
from output.card import card
from output.summary import summary
from settings_parsers import JobFilterAction, OutputSettingsAction, PeriodSettingsAction
from segments import Segment

REPO_ROOT = Path(__file__).resolve().parent.parent

@dataclass
class ParsedArgs:
    timecard_path: Path | None
    output_timezone: ZoneInfo | None
    alt_config: Path | None
    job_filter: Set[str] | None
    start_date: date | None
    end_date: date | None
    period: int | None
    period_settings: Tuple[date, int] | None
    output: OutputConfig | None
    macro: str | None
    print_config: bool

def parse_args() -> ParsedArgs:
    parser = argparse.ArgumentParser(prog="fluxcard",description="Summarize clock in sessions from the input file.\nUses settings from command line and config.toml")

    parser.add_argument("-i", "--input", dest="timecard_path", type=lambda x: Path(x) if x else None, help="Path to input file")
    parser.add_argument("-tz", "--timezone", dest="output_timezone", type=ZoneInfo, help="timezone to format output")
    parser.add_argument("-c","--config",dest="alt_config", type=lambda x: Path(x) if x else None, help="Alternate config file path")
    parser.add_argument("-j","--job",dest="job_filter",action=JobFilterAction,help='Job(s) to filter by seperated by comma "WebDev,Gardening". Clear filter set by config with "_". One job is required in period mode')


    parser.add_argument("start_date", nargs="?", type=parse_cli_start_date, help="Optinal start date, can use _ as a placeholder (YYYY-MM-DD)")
    parser.add_argument("end_date", nargs="?", type=date.fromisoformat, help="Optinal end date, not including the day itself (YYYY-MM-DD)")

    parser.add_argument("-p", "--period", type=int, help="Period index (0=current, 1=previous, etc.), replaces date filtering mode")
    parser.add_argument("--period-settings",nargs=2,action=PeriodSettingsAction, metavar=("ANCHOR_DATE","LENGTH"), help="anchor point date (YYYY-MM-DD) and period length in days used in period mode")
    parser.add_argument("-o", "--output",nargs=2,action=OutputSettingsAction, metavar=("DESTINATION","FORMAT"), help="where and what to output. Destination can be 'stdout' or a file path (absolute or cwd relative), format can be any string that is has an output function.")

    parser.add_argument('-m', "--macro", type=str, help="Macro to run, macros can be set in the config file to run commands with job filters and multiple output formats")
    parser.add_argument("--print-config",action="store_true", help="Print resolved configuration and exit")

    raw_args = parser.parse_args()

    return ParsedArgs(
        timecard_path=raw_args.timecard_path,
        output_timezone=raw_args.output_timezone,
        alt_config=raw_args.alt_config,
        job_filter=raw_args.job_filter,
        start_date=raw_args.start_date,
        end_date=raw_args.end_date,
        period=raw_args.period,
        period_settings=raw_args.period_settings,
        output=raw_args.output,
        macro=raw_args.macro,
        print_config=raw_args.print_config,
    )


def parse_cli_start_date(date_str: str|None):
    if date_str is None or date_str in ("_", ""):
        return None
    try:
        return date.fromisoformat(date_str)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid value '{date_str}', valid dates are 'YYYY-MM-DD' or '_'.")

def get_config(args: ParsedArgs) -> AppConfig:
    # check for alternate config parameter
    if args.alt_config is not None:
        alt_config_path = Path(args.alt_config).resolve()
        if not alt_config_path.exists():
            raise FluxCardInputError(f'config file at "{alt_config_path}" does not exist')
        return AppConfig.load(alt_config_path)
    # if no alternate, use the standard config file
    config_input_path = REPO_ROOT / "config.toml"
    if config_input_path.exists():
        return AppConfig.load(config_input_path)
    # if no standard, use empty config
    return AppConfig()

def get_input_path(args: ParsedArgs, config: AppConfig):
    
    if args.timecard_path is not None:
        input_path = Path(args.timecard_path).resolve()
    else:
        # grab config timecard file
        input_path = config.timecard_path
        if input_path is None:
            raise FluxCardInputError('"timecard_path" must be specified in config or given as a command line argument')
    
    if not input_path.exists():
        raise FluxCardInputError(f"file not found: {input_path}")
    if not input_path.is_file():
        raise FluxCardInputError(f"timecard file is not a file: {input_path}")
    if not os.access(input_path, os.R_OK):
        raise FluxCardInputError(f"Do not have permission to read file: {input_path}")
    return input_path

def get_output_timezone(args: ParsedArgs, config: AppConfig) -> ZoneInfo:
    if args.output_timezone is not None:
        return args.output_timezone
    if config.output_timezone is not None:
        return config.output_timezone
    
    raise FluxCardInputError('no output timezone specified in cli or config, please specify a timezone')

def get_macro_config(args: ParsedArgs, config: AppConfig) -> MacroConfig | None:
    if args.macro is None:
        return None
    if args.macro in config.macros:
        return config.macros[args.macro]
    
    raise FluxCardInputError(f"'{args.macro}' is not a defined macro\ncheck your spelling, check which config file you are using, or check that it is actually defined")
    
    


def get_job_filter(args: ParsedArgs, macro_config: MacroConfig | None, config: AppConfig) -> Set[str] | None:
    # for all places, None means not set, empty set means explicit no filter, any other set is a filter
    # the return value of this function is any set filter or None for no filter

    if args.job_filter is not None:
        if len(args.job_filter) == 0:
            return None
        return args.job_filter
    
    if macro_config is not None:
        return macro_config.job_filter

    if config.default_job is not None:
        return {config.default_job}


def get_period_settings(args: ParsedArgs, job_filter: str, config: AppConfig):
    job_config = config.job_config(job_filter)

    if args.period_settings is not None:
        return args.period_settings
    
    if job_config.period_anchor is None and job_config.period_length is None:
        raise FluxCardInputError(f'period settings not given, please specify with --period-settings cli option or [jobs.{job_filter}] period_anchor and period_length config settings')
    if job_config.period_anchor is None:
        raise FluxCardInputError(f'anchor missing from [jobs.{job_filter}] section in config')
    if job_config.period_length is None:
        raise FluxCardInputError(f'length missing from [jobs.{job_filter}] section in config')
    
    return job_config.period_anchor, job_config.period_length


def get_period_parameter(args: ParsedArgs, macro_config: MacroConfig | None) -> int | None:
    if args.period is not None:
        return args.period
    if macro_config is not None:
        return macro_config.period
    
    return None
    

def get_date_filters(args: ParsedArgs, macro_config: MacroConfig | None, job_filter: Set[str] | None, config: AppConfig):
    period = get_period_parameter(args,macro_config)
    if period is not None and (args.start_date or args.end_date):
        # if a period is specified and dates are specified, disallow it
        raise FluxCardInputError("Cannot use --period while also using date filter")

    
    if period is not None:
        # only allow one job in the filter here
        if job_filter is None or len(job_filter) > 1:
            raise FluxCardInputError('in period mode, only one job filter is allowed. If you only have one job, use the default_job config option to set the filter')
        job_filter_single = job_filter.pop()

        # grab the period settings from job config or command line
        period_anchor, period_length = get_period_settings(args, job_filter_single,config)
            
        # then come up with the start and end date
        start_date, end_date = calulate_period_date_range(period_anchor, period_length, period)
        
    else:
        # date filtering, straight use them
        start_date = args.start_date
        end_date = args.end_date

        if start_date is not None and end_date is not None and start_date >= end_date:
            raise FluxCardInputError('start date is after or the same as end date, no results would show')
    
    return start_date, end_date

def calulate_period_date_range(period_anchor: date, period_length: int, period_offset: int):
    # how many days since the anchor (can be negative)
    days_since_anchor = (date.today() - period_anchor).days
    # which period is today a part of?
    current_period_index = floor(days_since_anchor / period_length)
    # offset index by the user's input (0 current, 1 previous, so on)
    target_period_index = current_period_index - period_offset
    # shift that many days from the anchor
    start_date = period_anchor + timedelta(days=target_period_index*period_length)
    end_date = start_date + timedelta(days=period_length)

    return start_date, end_date


def get_outputs(args: ParsedArgs, macro_config: MacroConfig | None) -> List[OutputConfig]:
    # if args.outputs
    if args.output is not None:
        return [args.output]

    if macro_config is not None:
        return macro_config.outputs or []
    
    return []



def check_file_terminator(input_path: Path) -> None:
    """Check that the file terminates properly, will raise an error if not"""
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


def read_segment_lines(input_path: Path) -> Iterator[Tuple[Tuple[Path, int], List[str]]]:
    """Yields each block between lines with ==
    Note that this is very sensitive to lines, if the split line isn't exactly ==, it won't split it"""
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
    if not line.startswith(prefix):
        raise ValueError(f"Parsing Error. {loc_info[0]}:{loc_info[1]} in time line must begin with a '{prefix}' character")
    try:
        return datetime.fromisoformat(line[len(prefix):])
    except ValueError as e:
        e.add_note(f"occured at {loc_info[0]}:{loc_info[1]}")
        raise e

def parse_timecard_segment(lines: List[str], loc_info: Tuple[Path,int], tz: ZoneInfo):
    if len(lines) == 0:
            raise ValueError(f"Parsing Error. {loc_info[0]}:{loc_info[1]} empty record marked by consectutive == lines")
    if len(lines) < 4:
        raise ValueError(f"Parsing Error. {loc_info[0]}:{loc_info[1]} not enough lines in this record, expecting lines job, intime, outtime, at least one description line (can be empty)")

    job = lines[0]
    in_line = lines[1]
    out_line = lines[2]
    description = ";;".join(lines[3:])
    local_in = parse_timestamp_line(in_line,(loc_info[0],loc_info[1]+1),'>').astimezone(tz)
    local_out = parse_timestamp_line(out_line,(loc_info[0],loc_info[1]+2),'<').astimezone(tz)
    
    return Segment(job,local_in,local_out,description)


def split_across_midnight(segment: Segment, tz: ZoneInfo):
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


def parse_segments(segments: Iterator[Tuple[Tuple[Path,int],List[str]]],output_timezone: ZoneInfo) -> Iterator[Segment]:
    for loc_info, lines in segments:
        segment = parse_timecard_segment(lines,loc_info,output_timezone)
        yield from split_across_midnight(segment,output_timezone)

def job_filter_segments(segments: Iterator[Segment],job: Set[str] | None) -> Iterator[Segment]:
    if job is None:
        return segments
    
    return (s for s in segments if s.job in job)

def date_filter_segments(segments: Iterator[Segment],start_date: date | None, end_date: date | None) -> Iterator[Segment]:
    if start_date is None and end_date is None:
        yield from segments
    
    for s in segments:
        dat = s.inTime.date()
        if (start_date is None or start_date <= dat) and (end_date is None or dat < end_date):
            yield s


def group_segments_by_job_date(segments: Iterator[Segment]) -> Dict[str,Dict[date,List[Segment]]]:
    groups: Dict[str,Dict[date,List[Segment]]] = defaultdict(lambda: defaultdict(list))
    
    for s in segments:
        groups[s.job][s.inTime.date()].append(s)

    return groups

def group_segments_by_date(segments: Iterator[Segment]) -> Dict[date,List[Segment]]:
    groups: Dict[date,List[Segment]] = defaultdict(list)
    
    for s in segments:
        groups[s.inTime.date()].append(s)

    return groups



def main():
    try:
        args = parse_args()
        config = get_config(args)
        input_path = get_input_path(args, config)
        output_timezone = get_output_timezone(args, config)
        macro_config = get_macro_config(args,config)
        job_filter = get_job_filter(args, macro_config, config)
        start_date, end_date = get_date_filters(args, macro_config, job_filter, config)
        outputs = get_outputs(args, macro_config)
    except FluxCardInputError as e:
        raise e
        # print(e, file=sys.stderr)
        # exit(1)
    except Exception as e:
        e.add_note('this should probably be added as a FluxCardInputError')
        raise e
    except SystemExit:
        raise

    if args.print_config:
        print('using the following settings')
        print('input file:', input_path)
        print('output timezone:', output_timezone)
        print('job:', job_filter)
        print('start date:', start_date)
        print('end date:', end_date)
        print('outputs:')
        for o in outputs:
            print(' ',o.output_format,'at',o.output_str())
            
        exit(0)

    check_file_terminator(input_path)
    # file ends properly, lets read some segments
    splits = read_segment_lines(input_path)
    segments = date_filter_segments(job_filter_segments(parse_segments(splits,output_timezone),job_filter),start_date,end_date)
    data = group_segments_by_date(segments)

    for o in outputs:
        with o.open_stream() as stream:
            if o.output_format == 'card':
                card(stream,data)
            elif o.output_format == 'summary':
                summary(stream,data)


if __name__ == "__main__":
    main()
