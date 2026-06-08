


from collections import defaultdict
from datetime import date
import itertools
from typing import Dict, Iterable, List

from ..segments import Segment



def group_by_date(segments: Iterable[Segment]) -> Dict[date, List[Segment]]:
    """Group the segments by date, expects the segments to be sorted by inTime, iterating through the output will result in sorted dates"""
    # since it is already sorted by inTime, consequently date
    # use groupby
    groups = itertools.groupby(segments,key=lambda x: x.inTime.date())
    # now turn it into a dictionary
    return {date_key: list(segment_group) for date_key, segment_group in groups}


def group_by_job(segments: Iterable[Segment]) -> Dict[str,List[Segment]]:
    """Group the segments by job, keeps the sorted order within groups"""
    groups: Dict[str,List[Segment]] = defaultdict(list)
    
    for s in segments:
        groups[s.job].append(s)

    return groups


def group_by_job_date(segments: Iterable[Segment]) -> Dict[str,Dict[date,List[Segment]]]:
    """Group the segments by job and sub-group by date, expects the segments to be sorted by inTime, iterating through each sub-group will result in sorted dates"""
    groups: Dict[str,Dict[date,List[Segment]]] = defaultdict(lambda: defaultdict(list))
    
    for s in segments:
        groups[s.job][s.inTime.date()].append(s)

    return groups


def group_by_date_job(segments: Iterable[Segment]) -> Dict[date,Dict[str,List[Segment]]]:
    """Group the segments by date and sub-group by job, expects the segments to be sorted by inTime, iterating will result in sorted dates"""
    groups: Dict[date,Dict[str,List[Segment]]] = defaultdict(lambda: defaultdict(list))
    
    for s in segments:
        groups[s.inTime.date()][s.job].append(s)

    return groups
