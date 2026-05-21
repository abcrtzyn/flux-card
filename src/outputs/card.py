from datetime import timedelta
from io import TextIOWrapper
from typing import List

from output_registry import register_formatter
from processors.grouping import group_by_date
from processors.reductions import total
from segments import Segment

def format_timedelta(x: timedelta):
    "Quick function for formatting a timedelta"
    s = int(x.total_seconds())
    hr,s = divmod(s,3600)
    mn,s = divmod(s,60)

    return f"{hr}:{mn:02}:{s:02}"


@register_formatter("card")
def output_card(file: TextIOWrapper, data: List[Segment]):
    """My format for pasting into a formatted Apple pages document, sort of a tsv"""

    grouped = group_by_date(data)
    total_hours = total(data)

    file.write(f'\tIn\tOut\tHours\n')
    
    for dat, segs in grouped.items():
        
        # day_total = sum((s.elapsed() for s in segs), timedelta(0))

        
        # file.write(f"{dat.strftime('%a, %b %d %Y'):16s}  {day_total.total_seconds()/3600:.2f}\n");
        file.write(f"{dat.strftime('%a, %b %d %Y'):16s}\n");

        for seg in segs:
            # file.write(f"{seg.inTime.astimezone(pytz.timezone(output_timezone)).strftime('%-I %M %p')}     {seg.outTime.astimezone(pytz.timezone(output_timezone)).strftime('%-I %M %p')}\n")
            file.write(f"\t{seg.inTime.strftime('%-I:%M %p')}\t{seg.outTime.strftime('%-I:%M %p')}\t{str(seg.elapsed)}\n")
            
    file.write(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
    file.write(f"Total\t\t\t{format_timedelta(total_hours)}\n\n\n")
