

from io import TextIOWrapper
from typing import List

from ..output_registry import register_formatter
from ..processors.formaters import timedelta_HH_mm_ss
from ..processors.reductions import total
from ..segments import Segment


@register_formatter("total")
def print_total(file: TextIOWrapper, data: List[Segment]):
    
    total_hours = total(data)

    file.write(f'{timedelta_HH_mm_ss(total_hours)}\n')

    