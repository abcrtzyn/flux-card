
from typing import List, TextIO

from ..output_registry import register_formatter
from ..processors.grouping import group_by_date
from ..processors.reductions import total
from ..segments import Segment

@register_formatter("summary")
def summary(file: TextIO, data: List[Segment], single_line_description: bool = False, single_line_newline_delimeter: str = ';'):
    
    grouped = group_by_date(data)

    for dat, segs in grouped.items():
        
        day_total = total(segs)

        file.write(f"{dat.strftime('%a, %b %d %Y'):16s}  {str(day_total):>8s}\n");
        
        for seg in segs:
            if single_line_description:
                description = single_line_newline_delimeter.join(seg.description.splitlines())
                file.write(f"{seg.inTime.strftime('%-I:%M:%S%p%z'):>16s}    {str(seg.elapsed):>8s}    {description}\n")
            else:
                for line_num, line in enumerate(seg.description.splitlines()):
                    if line_num == 0:
                        file.write(f"{seg.inTime.strftime('%-I:%M:%S%p%z'):>16s}    {str(seg.elapsed):>8s}    {line}\n")
                    else:
                        file.write(f'{'':>32s}{line}\n')
        