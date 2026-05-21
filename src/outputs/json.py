
from io import TextIOWrapper
from typing import List

from output_registry import register_formatter
from segments import Segment


@register_formatter("json")
def output_json(file: TextIOWrapper, data: List[Segment]):
    pass

    # there are several ways to do this, group by job, group by date, just print it out raw.
    # do we include the elapsed times or not, how about in the groups
    # how many of these options do we pass onto the user or just create different output formats instead
    # how do we output datetimes and timedeltas, as dictionaries?
    