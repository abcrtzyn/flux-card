
from argparse import Action, ArgumentError, ArgumentParser, Namespace
from datetime import date
from typing import Any, Sequence


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
