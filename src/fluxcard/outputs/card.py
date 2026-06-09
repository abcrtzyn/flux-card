
from typing import List, TextIO

from ..output_registry import register_formatter
from ..processors.formaters import timedelta_HH_mm_ss
from ..processors.grouping import group_by_date
from ..processors.reductions import total
from ..segments import Segment


@register_formatter("card")
def output_card(file: TextIO, data: List[Segment]):
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
    file.write(f"Total\t\t\t{timedelta_HH_mm_ss(total_hours)}\n\n\n")
