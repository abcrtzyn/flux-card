# visualization (grouped by date, sorted by intime)
# Can use different colors for different jobs

# Tue, Jan 14: ░░░░░░░░░░████░░░░██░░░░░░░░░░░░ (Total: 6.4h)
# Wed, Jan 15: ░░░░░░░░░░░░░░░░░░░░░░░░░██░░░░░ (Total: 2.0h)
#              (░ = Off, █ = Logged Hours)



from io import TextIOWrapper
from math import ceil
from typing import List

from output_registry import register_formatter
from processors.conversion import time_to_seconds_of_day
from processors.daterange import daterange
from processors.grouping import group_by_date
from processors.reductions import total
from segments import Segment


section_length = 3600 # one hour
# section_length = 1800 # half hour
# section_length = 900 # quarter hour

sections_per_day = ceil(86400 / section_length)


@register_formatter("visualization")
def summary(file: TextIOWrapper, data: List[Segment],fill_in: bool = True):
    
    grouped = group_by_date(data)

    # Get the first key (Minimum Date)
    min_date = next(iter(grouped))

    # Get the last key (Maximum Date)
    max_date = next(reversed(grouped))
    

    for d in daterange(min_date,max_date):
        file.write(f'{d.strftime('%a, %b %d %Y')}: ')
        if d not in grouped:
            file.write(f'{'░'*sections_per_day} (Total: 0h)\n')
            continue
        # we have some data here
        segments = grouped[d]

        # for each section, determine if the block should be filled or not
        # we will be generous and go up to the nearest whole section.

        day_map = [False] * sections_per_day

        for segment in segments:
            intime = time_to_seconds_of_day(segment.inTime)
            outtime = time_to_seconds_of_day(segment.outTime)

            # light up any segments of day_map that include intime, outtime, or anywhere in between
            in_segment = intime // section_length
            out_segment = outtime // section_length + 1

            day_map[in_segment:out_segment] = [True]*(out_segment-in_segment)
        

        for c in day_map:
            file.write(f'{'█' if c else '░'}')

        day_total = total(segments)

        file.write(f' (Total: {day_total.total_seconds()/3600:.2f}h)\n')

