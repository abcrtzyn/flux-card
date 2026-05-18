
from argparse import Action, ArgumentError, ArgumentParser, Namespace
from datetime import date
from pathlib import Path
from typing import Any, Sequence

from config import OutputConfig


class PeriodSettingsAction(Action):
    def __call__(self, parser: ArgumentParser, namespace: Namespace, values: str | Sequence[Any] | None, option_string: str | None=None):
        try:
            anchor = date.fromisoformat(values[0]) # pyright: ignore[reportUnknownArgumentType, reportOptionalSubscript]
        except ValueError:
            raise ArgumentError(self, "period anchor must be a valid date")
        try:
            length = int(values[1]) # pyright: ignore[reportUnknownArgumentType, reportOptionalSubscript]
        except ValueError:
            raise ArgumentError(self, "period length must be a integer")
        
        setattr(namespace, self.dest, (anchor, length))

class OutputSettingsAction(Action):
    def __call__(self, parser: ArgumentParser, namespace: Namespace, values: str | Sequence[Any] | None, option_string: str | None=None):
        try:
            oc = OutputConfig.from_args(values[0],values[1],Path('.')) # pyright: ignore[reportUnknownArgumentType, reportOptionalSubscript]
        except Exception as e:
            e.add_note('could not parse output flag because of the above error')
            raise e
    
        setattr(namespace, self.dest, oc)
