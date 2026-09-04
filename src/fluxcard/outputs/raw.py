
from typing import List, TextIO

from ..output_registry import register_formatter
from ..segments import Segment


@register_formatter("raw")
def output_raw(file: TextIO, data: List[Segment]):
    """Outputs in the same format as the Clock input file
    Useful if you want to do some sort of filtering
    Note that the midnight crossing periods will be seperated in this file"""

    file.write(f'==')

    for seg in data:
        file.write('\n')
        file.write(f'{seg.job}\n')
        file.write(f'>{seg.inTime.isoformat()}\n')
        file.write(f'<{seg.outTime.isoformat()}\n')
        file.write(f'{seg.description}\n==')
        