
from argparse import Action, ArgumentError, ArgumentParser, Namespace
from datetime import date
from pathlib import Path
from typing import Any, Sequence, cast

from config import OutputConfig



class OutputSettingsAction(Action):
    def __call__(self, parser: ArgumentParser, namespace: Namespace, values: str | Sequence[Any] | None, option_string: str | None=None):
        try:
            oc = OutputConfig.from_args(values[0],values[1],Path('.')) # pyright: ignore[reportUnknownArgumentType, reportOptionalSubscript]
        except Exception as e:
            e.add_note('could not parse output flag because of the above error')
            raise e
    
        setattr(namespace, self.dest, oc)

class JobFilterAction(Action):
    def __call__(self, parser: ArgumentParser, namespace: Namespace, values: str | Sequence[Any] | None, option_string: str | None=None):
        if not values or values == "_":
            # Interpret "_" as an explicit command to clear all filters
            setattr(namespace, self.dest, set())
            return

        # Split comma-separated inputs and strip whitespace
        job_set = {item.strip() for item in cast(str,values).split(",") if item.strip()}
        
        if '' in job_set or '_' in job_set:
            raise ArgumentError(self,'Not sure how to handle "_" in the job filter list. It doesn\'t make sense to set a filter and clear the filter at the same time')

        setattr(namespace, self.dest, job_set)
