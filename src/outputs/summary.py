from datetime import date, timedelta
from io import TextIOWrapper
from typing import Dict, List

from output_registry import register_formatter
from segments import Segment

@register_formatter("summary")
def summary(file: TextIOWrapper, data: Dict[date,List[Segment]]):
    
    for dat in sorted(data.keys()):
        segs = data[dat]
        day_total = sum((s.elapsed() for s in segs), timedelta(0))

        file.write(f"{dat.strftime('%a, %b %d %Y'):16s}  {str(day_total):>8s}\n");
        
        for seg in segs:
            file.write(f"{seg.inTime.strftime('%-I:%M:%S%p%z'):>16s}    {str(seg.elapsed()):>8s}   {seg.description}\n")
        