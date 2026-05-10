#!/usr/bin/env python3

import argparse
from collections import defaultdict
from datetime import datetime, time, timedelta, date
import os
from pathlib import Path
import tomllib
from typing import Any, List, Dict
from zoneinfo import ZoneInfo

from segments import Segment


REPO_ROOT = Path(__file__).resolve().parent.parent

def load_config() -> Dict[str,Any]:
    config_input_path = REPO_ROOT / "config.toml"
    if not config_input_path.exists():
        return {}
    
    with open(config_input_path, "rb") as f:
        return tomllib.load(f)

def parse_cli_start_date(date_str: str|None):
    if date_str is None or date_str in ("_", ""):
        return None
    return date.fromisoformat(date_str)
    

def format_timedelta(x: timedelta):
    "Quick function for formatting a timedelta"
    s = int(x.total_seconds())
    hr,s = divmod(s,3600)
    mn,s = divmod(s,60)

    return f"{hr}:{mn:02}:{s:02}"


def main():
    config = load_config()

    parser = argparse.ArgumentParser(prog="fluxcard")

    parser.add_argument("-i", "--input", dest="timecard_path", help="Path to input file")
    parser.add_argument("-tz", "--timezone", dest="output_timezone", type=ZoneInfo, help="timezone to format output")

    parser.add_argument("start_date", nargs="?", type=parse_cli_start_date, help="Optinal start date, can use _ as a placeholder (YYYY-MM-DD)")
    parser.add_argument("end_date", nargs="?", type=date.fromisoformat, help="Optinal end date, not including the day itself (YYYY-MM-DD)")

    args = parser.parse_args()    

    if hasattr(args,'timecard_path'):
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

    if hasattr(args,"output_timezone"):
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

    start_date = args.start_date
    end_date = args.end_date

    if start_date >= end_date:
        print('start date is after or the same as end date, no results would show')
        exit(1)


    print('using the following settings')
    print('input file:', input_path)
    print('output timezone:', output_timezone)
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
