# visualization (grouped by date, sorted by intime)
# Can use different colors for different jobs

# Tue, Jan 14: ░░░░░░░░░░████░░░░██░░░░░░░░░░░░ (Total: 6.4h)
# Wed, Jan 15: ░░░░░░░░░░░░░░░░░░░░░░░░░██░░░░░ (Total: 2.0h)
#              (░ = Off, █ = Logged Hours)




from io import TextIOWrapper
from typing import List

from output_registry import register_formatter
from processors.daterange import daterange
from processors.grouping import group_by_date
from processors.reductions import total
from segments import Segment


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
            file.write('░░░░░░░░░░░░░░░░░░░░░░░░ (Total: 0h)\n')
            continue
        # we have some data here
        segments = grouped[d]

        # for each hour, determine if the block should be filled or not
        hours_map = [False]*24
        
        for segment in segments:
            hours_map[segment.inTime.hour:segment.outTime.hour+1] = [True]*(segment.outTime.hour-segment.inTime.hour+1)
        

        for c in hours_map:
            file.write(f'{'█' if c else '░'}')

        day_total = total(segments)

        file.write(f' (Total: {day_total.total_seconds()/3600:.2f}h)\n')

