
from io import TextIOWrapper
from typing import List

from output_registry import register_formatter
from segments import Segment


@register_formatter("csv")
def output_csv(file: TextIOWrapper, data: List[Segment],job_column: bool = True):
    
    file.write(f'{'job,' if job_column else ''}date,in,out,description\n')

    # print(data)
