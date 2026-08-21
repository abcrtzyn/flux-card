
from typing import List, TextIO

from ..output_registry import register_formatter
from ..processors.formatters import timedelta_HH_mm_ss
from ..segments import Segment


@register_formatter("mdtable")
def output_markdown_table(file: TextIO, data: List[Segment],job_column: bool = True):
    """Create a markdown table with the raw date, in time, out time, elapsed time, job, and description.
    The job column can be turned off by the user"""

    file.write(f'| date | in   | out  | elapsed | {'job  | ' if job_column else ''}descrption |\n')
    file.write(f'| :--- | :--- | :--- | :---    | {':--- | ' if job_column else ''}:---       |\n')

    for seg in data:
        date = seg.inTime.date()
        in_time = f'{seg.inTime.strftime('%-I:%M:%S %p')}'
        out_time = f'{seg.outTime.strftime('%-I:%M:%S %p')}'
        elapsed = f'{timedelta_HH_mm_ss(seg.elapsed)}'
        job = seg.job
        # making sure to escape any double quotes, newlines stay the same
        description = ';'.join(seg.description.splitlines())

        file.write(f'| {date} | {in_time} | {out_time} | {elapsed} | {f'{job} | ' if job_column else ''}{description}\n')

    # print(data)
