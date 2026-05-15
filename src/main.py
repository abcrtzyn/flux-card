#!/usr/bin/env python3

import argparse
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, time, timedelta, date # pyright: ignore[reportPrivateUsage]
from math import floor
import os
from pathlib import Path
import sys
from typing import Iterator, List, Dict, Tuple
from zoneinfo import ZoneInfo

from config import AppConfig, JobConfig
from error import FluxCardInputError
from period_settings_parser import PeriodSettingsAction
from segments import Segment

REPO_ROOT = Path(__file__).resolve().parent.parent

@dataclass
class ParsedArgs:
    timecard_path: Path | None
    output_timezone: ZoneInfo | None
    alt_config: Path | None
    job_filter: str | None
    start_date: date | None
    end_date: date | None
    period: int | None
    period_settings: Tuple[date, int] | None

def parse_args() -> ParsedArgs:
    parser = argparse.ArgumentParser(prog="fluxcard",description="Summarize clock in sessions from the input file.\nUses settings from command line and config.toml")

    parser.add_argument("-i", "--input", dest="timecard_path", type=lambda x: Path(x) if x else None, help="Path to input file")
    parser.add_argument("-tz", "--timezone", dest="output_timezone", type=ZoneInfo, help="timezone to format output")
    parser.add_argument("-c","--config",dest="alt_config", type=lambda x: Path(x) if x else None, help="Alternate config file path")
    parser.add_argument("-j","--job",dest="job_filter",help="Job to filter by, required in period mode")


    parser.add_argument("start_date", nargs="?", type=parse_cli_start_date, help="Optinal start date, can use _ as a placeholder (YYYY-MM-DD)")
    parser.add_argument("end_date", nargs="?", type=date.fromisoformat, help="Optinal end date, not including the day itself (YYYY-MM-DD)")

    parser.add_argument("-p", "--period", type=int, help="Period index (0=current, 1=previous, etc.), replaces date filtering mode")
    parser.add_argument("--period-settings",nargs=2,action=PeriodSettingsAction, metavar=("ANCHOR_DATE","LENGTH"), help="anchor point date (YYYY-MM-DD) and period length in days used in period mode")

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

def get_job_filter(args: ParsedArgs, config: AppConfig):
    if args.job_filter is not None:
        if args.job_filter == '_':
            return None
        return args.job_filter
    
    if config.default_job is not None:
        return config.default_job
    
    return None


def get_period_settings(args: ParsedArgs, job_filter: str | None, job_config: JobConfig):
    if job_filter is None:
        raise FluxCardInputError('period mode requires a job filter set by -j [job] or in the config as default_job')

    if args.period_settings is not None:
        return args.period_settings
    
    if job_config.period_anchor is None and job_config.period_length is None:
        raise FluxCardInputError(f'period settings not given, please specify with --period-settings cli option or [jobs.{job_filter}] period_anchor and period_length config settings')
    if job_config.period_anchor is None:
        raise FluxCardInputError(f'anchor missing from [jobs.{job_filter}] section in config')
    if job_config.period_length is None:
        raise FluxCardInputError(f'length missing from [jobs.{job_filter}] section in config')
    
    return job_config.period_anchor, job_config.period_length


def get_date_filters(args: ParsedArgs, job_filter: str | None, job_config: JobConfig):
    if args.period is not None and (args.start_date or args.end_date):
        raise FluxCardInputError("Cannot use --period while also using date filter")

    if args.period is not None:
        period_anchor, period_length = get_period_settings(args, job_filter, job_config)
            
        # then come up with the start and end date
        start_date, end_date = calulate_period_date_range(period_anchor, period_length, args.period)
        
    else:
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


def format_timedelta(x: timedelta):
    "Quick function for formatting a timedelta"
    s = int(x.total_seconds())
    hr,s = divmod(s,3600)
    mn,s = divmod(s,60)

    return f"{hr}:{mn:02}:{s:02}"


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

def job_filter_segments(segments: Iterator[Segment],job: str | None) -> Iterator[Segment]:
    if job is None:
        return segments
    
    return (s for s in segments if s.job == job)

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
        job_filter = get_job_filter(args, config)
        job_config = config.job_config(job_filter)
        start_date, end_date = get_date_filters(args, job_filter, job_config)
    except FluxCardInputError as e:
        print(e, file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        e.add_note('this should probably be added as a FluxCardInputError')
        raise e
    except SystemExit:
        raise

    print('using the following settings')
    print('input file:', input_path)
    print('output timezone:', output_timezone)
    print('job:', job_filter)
    print('start date:', start_date)
    print('end date:', end_date)

    # exit()

    check_file_terminator(input_path)
    # file ends properly, lets read some segments
    splits = read_segment_lines(input_path)
    segments = date_filter_segments(job_filter_segments(parse_segments(splits,output_timezone),job_filter),start_date,end_date)
    grouped_segs = group_segments_by_job_date(segments)

    
    with open("summary.txt",'w') as summary, open("timecard.txt",'w') as card:
        # for each job
        for job, date_groups in grouped_segs.items():
            all_job_deltas = [s.elapsed() for day in date_groups.values() for s in day]
            total_hours = sum(all_job_deltas, timedelta(0))

            # write job headers
            summary.write(f'{job:13s}  {format_timedelta(total_hours):>10s}\n')
            card.write(f'{job}\n')
            card.write(f'\tIn\tOut\tHours\n')
            # if OUT:
            #     print(f'{job:13s}  {format_timedelta(total_hours):>10s}')
            # else:
            #     print(f'{job}')
            # now list out each date and its segments
            for dat in sorted(date_groups.keys()):
                segs = date_groups[dat]
                day_total = sum((s.elapsed() for s in segs), timedelta(0))

                summary.write(f"{dat.strftime('%a, %b %d %Y'):16s}  {str(day_total):>8s}\n");
                # card.write(f"{dat.strftime('%a, %b %d %Y'):16s}  {day_total.total_seconds()/3600:.2f}\n");
                card.write(f"{dat.strftime('%a, %b %d %Y'):16s}\n");

                # if OUT: 
                #     print(f"{dat.strftime('%a, %b %d %Y'):16s}  {str(day_total):>8s}")
                # else:
                #     print(f"{dat.strftime('%a, %b %d %Y'):16s}  {day_total.total_seconds()/3600:.2f}")
                
                for seg in segs:
                    summary.write(f"{seg.inTime.strftime('%-I:%M:%S%p%z'):>16s}    {str(seg.elapsed()):>8s}   {seg.description}\n")
                    # card.write(f"{seg.inTime.astimezone(pytz.timezone(output_timezone)).strftime('%-I %M %p')}     {seg.outTime.astimezone(pytz.timezone(output_timezone)).strftime('%-I %M %p')}\n")
                    card.write(f"\t{seg.inTime.strftime('%-I:%M %p')}\t{seg.outTime.strftime('%-I:%M %p')}\t{str(seg.elapsed())}\n")
                    # if OUT:
                    #     print(f"{seg.inTime.strftime('%-I:%M:%S%p%z'):>16s}   {str(seg.elapsed()):>8s}   {seg.description}")
                    # else:
                    #     print(f"{seg.inTime.strftime('%-I %M %p')}     {seg.outTime.strftime('%-I %M %p')}")
            
            card.write(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
            card.write(f"Total\t\t\t{format_timedelta(total_hours)}\n\n\n")


if __name__ == "__main__":
    main()
