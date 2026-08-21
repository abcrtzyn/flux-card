


from typing import List, TextIO

from fluxcard.processors.grouping import group_by_job

from ..output_registry import register_formatter
from ..processors.formatters import timedelta_HH_mm_ss
from ..processors.reductions import total
from ..segments import Segment


@register_formatter("jobtotal")
def total_table(file: TextIO, data: List[Segment]):
    grouped_data = {k: total(x) for k,x in group_by_job(data).items()}

    max_length = max([len(x) for x in grouped_data.keys()])

    for k,v in grouped_data.items():
        file.write(f'{k:<{max_length}s}     {timedelta_HH_mm_ss(v):>8s}\n')
    

    