


from datetime import date, timedelta
from io import TextIOWrapper
from typing import Dict, List

from output_registry import register_formatter
from segments import Segment


def format_timedelta(x: timedelta):
    "Quick function for formatting a timedelta"
    s = int(x.total_seconds())
    hr,s = divmod(s,3600)
    mn,s = divmod(s,60)

    return f"{hr}:{mn:02}:{s:02}"



@register_formatter("total")
def print_total(file: TextIOWrapper, data: Dict[date,List[Segment]], argument: str | None = None):
    all_job_deltas = [s.elapsed() for day in data.values() for s in day]
    total_hours = sum(all_job_deltas, timedelta(0))

    file.write(f'{format_timedelta(total_hours)}\n')

    