
from dataclasses import dataclass, field
from datetime import datetime, timedelta

@dataclass
class Segment:
    job: str;
    inTime: datetime;
    outTime: datetime;
    description: str;
    elapsed: timedelta = field(init=False)

    def __post_init__(self):
        self.elapsed = self.outTime-self.inTime
    