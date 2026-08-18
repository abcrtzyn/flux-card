# visualization (grouped by date, sorted by intime)
# Can use different colors for different jobs

# Tue, Jan 14: ░░░░░░░░░░████░░░░██░░░░░░░░░░░░ (Total: 6.4h)
# Wed, Jan 15: ░░░░░░░░░░░░░░░░░░░░░░░░░██░░░░░ (Total: 2.0h)
#              (░ = Off, █ = Logged Hours)




from datetime import date
from math import ceil
from typing import List, TextIO

from ..output_registry import register_formatter
from ..processors.conversion import time_to_seconds_of_day
from ..processors.daterange import daterange
from ..processors.grouping import group_by_date
from ..processors.reductions import total
from ..segments import Segment


section_length = 3600 # one hour
# section_length = 1800 # half hour
# section_length = 900 # quarter hour

sections_per_day = ceil(86400 / section_length)


@register_formatter("visualization")
def render_visualization(file: TextIO, data: List[Segment],fill_in: bool = True, use_date_filter: bool = False, filter_start_date: date | None = None, filter_end_date: date | None = None):
    
    grouped = group_by_date(data)

    # Get the first key (Minimum Date) or use the start date
    min_date = filter_start_date if use_date_filter and filter_start_date is not None else next(iter(grouped))

    # Get the last key (Maximum Date) or use the end date
    max_date = filter_end_date if use_date_filter and filter_end_date is not None else next(reversed(grouped))
    
    date_set = daterange(min_date,max_date) if fill_in else grouped

    for d in date_set:
        file.write(f'{d.strftime('%a, %b %d %Y')}: ')
        if fill_in and d not in grouped:
            # if we are in fill_in mode and the date doesn't have data, skip it.
            file.write(f'{'░'*sections_per_day} (Total: 0h)\n')
            continue
        # we have some data here
        segments = grouped[d]

        # do some processing with it

        # for each section, determine if the block should be filled or not
        # we will be generous and go up to the nearest whole section.

        day_map = [False] * sections_per_day

        for segment in segments:
            intime = time_to_seconds_of_day(segment.inTime)
            outtime = time_to_seconds_of_day(segment.outTime)

            # light up any segments of day_map that include intime, outtime, or anywhere in between
            in_segment = intime // section_length
            # ceiling division, to deal with edge cases
            out_segment = (outtime + section_length - 1) // section_length

            day_map[in_segment:out_segment] = [True]*(out_segment-in_segment)
        
        map_string = ''.join('█' if c else '░' for c in day_map)

        day_total = total(segments)

        file.write(f'{map_string} (Total: {day_total.total_seconds()/3600:.2f}h)\n')
