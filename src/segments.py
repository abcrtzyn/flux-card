
from dataclasses import dataclass
from datetime import datetime, timedelta

@dataclass
class Segment:
    job: str;
    inTime: datetime;
    outTime: datetime;
    description: str;
    
    def elapsed(self) -> timedelta:
        return self.outTime-self.inTime;
