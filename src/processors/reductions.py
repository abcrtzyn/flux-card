from datetime import timedelta
from typing import List

from segments import Segment


def total(data: List[Segment]) -> timedelta:
    """Returs the total time in a list of segments"""
    return sum([s.elapsed for s in data],timedelta(0))
