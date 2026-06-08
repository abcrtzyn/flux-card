from io import TextIOWrapper
from typing import List

from ..output_registry import register_formatter
from ..processors.grouping import group_by_date
from ..processors.reductions import total
from ..segments import Segment

@register_formatter("summary")
def summary(file: TextIOWrapper, data: List[Segment]):
    
    grouped = group_by_date(data)

    for dat, segs in grouped.items():
        
        day_total = total(segs)

        file.write(f"{dat.strftime('%a, %b %d %Y'):16s}  {str(day_total):>8s}\n");
        
        for seg in segs:
            file.write(f"{seg.inTime.strftime('%-I:%M:%S%p%z'):>16s}    {str(seg.elapsed):>8s}   {seg.description}\n")
        