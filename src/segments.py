
from datetime import datetime, timedelta


class Segment:
    job: str;
    inTime: datetime;
    outTime: datetime;
    description: str;

    def __init__(self, job: str, inTime: datetime, outTime: datetime, description: str):
        self.job = job;
        self.inTime = inTime;
        self.outTime = outTime;
        self.description = description;
    
    def elapsed(self) -> timedelta:
        return self.outTime-self.inTime;
