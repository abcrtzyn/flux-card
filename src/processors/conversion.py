


from datetime import datetime


def time_to_seconds_of_day(time: datetime) -> int:
    return time.hour * 3600 + time.minute * 60 + time.second
