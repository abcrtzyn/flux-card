


from datetime import timedelta
from io import TextIOWrapper
from typing import List

from output_registry import register_formatter
from processors.reductions import total
from segments import Segment


def format_timedelta(x: timedelta):
    "Quick function for formatting a timedelta"
    s = int(x.total_seconds())
    hr,s = divmod(s,3600)
    mn,s = divmod(s,60)

    return f"{hr}:{mn:02}:{s:02}"



@register_formatter("total")
def print_total(file: TextIOWrapper, data: List[Segment]):
    
    total_hours = total(data)

    file.write(f'{format_timedelta(total_hours)}\n')

    