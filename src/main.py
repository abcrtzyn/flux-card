#!/usr/bin/env python3

import argparse
from collections import defaultdict
from datetime import datetime, time, timedelta, date
from math import floor
import os
from pathlib import Path
import tomllib
from typing import Any, List, Dict, Tuple, cast
from zoneinfo import ZoneInfo

from period_settings_parser import PeriodSettingsAction
from segments import Segment


REPO_ROOT = Path(__file__).resolve().parent.parent

def parse_cli_start_date(date_str: str|None):
    if date_str is None or date_str in ("_", ""):
        return None
    try:
        return date.fromisoformat(date_str)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid value '{date_str}', valid dates are 'YYYY-MM-DD' or '_'.")
    

def format_timedelta(x: timedelta):
    "Quick function for formatting a timedelta"
    s = int(x.total_seconds())
    hr,s = divmod(s,3600)
    mn,s = divmod(s,60)

    return f"{hr}:{mn:02}:{s:02}"


def main():

    parser = argparse.ArgumentParser(prog="fluxcard",description="Summarize clock in sessions from the input file.\nUses settings from command line and config.toml")

    parser.add_argument("-i", "--input", dest="timecard_path", help="Path to input file")
    parser.add_argument("-tz", "--timezone", dest="output_timezone", type=ZoneInfo, help="timezone to format output")
    parser.add_argument("-c","--config",dest="alt_config",help="Alternate config file path")
    parser.add_argument("-j","--job",dest="job_filter",help="Job to filter by, required in period mode")


    parser.add_argument("start_date", nargs="?", type=parse_cli_start_date, help="Optinal start date, can use _ as a placeholder (YYYY-MM-DD)")
    parser.add_argument("end_date", nargs="?", type=date.fromisoformat, help="Optinal end date, not including the day itself (YYYY-MM-DD)")

    parser.add_argument("-p", "--period", type=int, help="Period index (0=current, 1=previous, etc.), replaces date filtering mode")
    parser.add_argument("--period-settings",nargs=2,action=PeriodSettingsAction, metavar=("ANCHOR_DATE","LENGTH"), help="anchor point date (YYYY-MM-DD) and period length in days used in period mode")

    args = parser.parse_args()

    ### CONFIG FILE
    if args.alt_config is not None:
        # check that given config file exists
        alt_config_path = Path(args.alt_config).resolve()
        if not alt_config_path.exists():
            print(f'config file at "{alt_config_path}" does not exist')
            exit(1)
        
        with open(alt_config_path, "rb") as f:
            config = tomllib.load(f)
    else:
        config_input_path = REPO_ROOT / "config.toml"
        if not config_input_path.exists():
            config: Dict[str,Any] = {}
    
        with open(config_input_path, "rb") as f:
            config = tomllib.load(f)

    ### INPUT PATH
    if args.timecard_path is not None:
        input_path = Path(args.timecard_path).resolve()
    else:
        # grab config timecard file
        if "timecard_path" not in config:
            print('"timecard_path" must be specified in config or given as a command line argument')
            exit(1)
        p = Path(config["timecard_path"]).expanduser()
        if p.is_absolute():
            input_path = p
        else:
            input_path = (REPO_ROOT / p).resolve()

    if not input_path.exists():
        print(f"file not found: {input_path}")
        exit(1)
    if not input_path.is_file():
        print(f"timecard file is not a file: {input_path}")
        exit(1)
    if not os.access(input_path, os.R_OK):
        print(f"Do not have permission to read file: {input_path}")
        exit(1)

    ### OUTPUT TIMEZONE
    if args.output_timezone is not None:
        output_timezone = args.output_timezone
    elif "output_timezone" in config:
        output_timezone = ZoneInfo(config["output_timezone"])
    else:
        output_timezone = datetime.now().astimezone().tzinfo
        if output_timezone is None:
            print('no output timezone specified in cli or config, tried to use system timezone but found none')
            print('please specify a timezone in the cli or config file')
            exit(1)
        print(f'warning, no output timezone specified in cli or config, using {output_timezone}')
    
    ### JOB FILTER
    if args.job_filter is not None:
        if args.job_filter == '_':
            job_filter = None
        job_filter = args.job_filter
    elif "default_job" in config:
        job_filter = config["default_job"]
    else:
        job_filter = None

    if job_filter is not None and "jobs" in config and job_filter in config["jobs"]:
        job_config = cast(Dict[str,Any],config["jobs"][job_filter])
    else:
        job_config: Dict[str,Any] = {}


    ### START AND END DATE FILTER (ALSO PERIODS)
    if args.period is not None and (args.start_date or args.end_date):
        print("Cannot use --period while also using date filter")
        exit(1)

    if args.period is not None:
        ### PERIOD SETTINGS
        if job_filter is None:
            print('period mode requires a job filter set by -j [job] or in the config as default_job')
            exit(1)

        if args.period_settings is not None:
            period_anchor, period_length = cast(Tuple[date,int],args.period_settings)
        else:
            if 'period_anchor' not in job_config and 'period_length' not in job_config:
                print(f'period settings not given, please specify with --period-settings cli option or [jobs.{job_filter}] period_anchor and period_length config settings')
                exit(1)
            if 'period_anchor' not in job_config:
                print(f'anchor missing from [jobs.{job_filter}] section in config')
                exit()
            period_anchor = job_config['period_anchor']
            if not isinstance(period_anchor,date):
                print(f"[jobs.{job_filter}] period_anchor must be a date in YYYY-MM-DD format, got '{period_anchor}'")
                exit()
            if 'period_length' not in job_config:
                print(f'length missing from [jobs.{job_filter}] section in config')
                exit()
            period_length = job_config['period_length']
            if not isinstance(period_length,int):
                print(f"[jobs.{job_filter}] length must be an integer, got a type {type(period_length).__name__}")
                exit()
            
        # then come up with the start and end date

        # how many days since the anchor (can be negative)
        days_since_anchor = (date.today() - period_anchor).days
        # which period is today a part of?
        current_period_index = floor(days_since_anchor / period_length)
        # offset index by the user's input (0 current, 1 previous, so on)
        target_period_index = current_period_index - args.period
        # shift that many days from the anchor
        start_date = period_anchor + timedelta(days=target_period_index*period_length)
        end_date = start_date + timedelta(days=period_length)
        
    else:
        start_date = args.start_date
        end_date = args.end_date

        if start_date is not None and end_date is not None and start_date >= end_date:
            print('start date is after or the same as end date, no results would show')
            exit(1)


    print('using the following settings')
    print('input file:', input_path)
    print('output timezone:', output_timezone)
    print('job:', job_filter)
    print('start date:', start_date)
    print('end date:', end_date)

    with open(input_path) as clock:
        txt = clock.read();

    txtSegments = [seg.strip() for seg in txt.split("==")];
    # make sure the last one is an empty string.
    if(txtSegments[-1] != ""):
        raise Exception("The file does not end with a double equals, are you still clocked in?");

    # Each string in txtSegments should look like this
    # """
    # Job
    # >2025-01-13T12:20:00-06:00
    # <2025-01-13T15:20:00-06:00
    # Description
    # possible multiple line descrption
    # """

    # Next, parse each segment
    segments: List[Segment] = list();
    
    # go through each time segment
    for text in txtSegments[1:-1]:
        lines = text.split("\n");
        # check that the zeroth begins with >
        if(lines[1][0] != ">"):
            raise Exception("not a valid clock in") #TODO Give a line number
        # check that the first begins with <
        if(lines[2][0] != "<"):
            raise Exception("not a valid clock out") #TODO Give a line number
        
        job = lines[0]

        # filter by job here.
        if job_filter is not None and job != job_filter:
            continue

        description = ';;'.join(lines[3:])
        # extract time values
        localInTime = datetime.fromisoformat(lines[1][1:]).astimezone(output_timezone)
        localOutTime = datetime.fromisoformat(lines[2][1:]).astimezone(output_timezone)

        current_start = localInTime
        
        # deal with in-outs that pass on multiple days
        while localOutTime.date() > current_start.date():
            # Create a midnight marker at 23:59:59.99 for the current day
            local_current = current_start
            end_of_day = local_current.replace(hour=23, minute=59, second=59)
            
            segments.append(Segment(job, current_start, end_of_day, description))
            
            # Set the start of the next segment to 00:00:00 of the following day
            next_day = local_current.date() + timedelta(days=1)
            current_start = datetime.combine(next_day, time.min, tzinfo=output_timezone)

        segments.append(Segment(job, current_start, localOutTime, description))


    # group by job and date
    grouped_segs: Dict[str,Dict[date,List[Segment]]] = defaultdict(lambda: defaultdict(list))

    
    for seg in segments:
        dat = seg.inTime.date();
        if (start_date is None or start_date <= dat) and (end_date is None or dat < end_date):
            # if the date is within the filter range
            grouped_segs[seg.job][dat].append(seg);


    # reduced_segs: Dict[str,Dict[date,timedelta]] = defaultdict(dict);
    # straight_hours: Dict[str, timedelta] = dict();

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
            # print();

if __name__ == "__main__":
    main()
