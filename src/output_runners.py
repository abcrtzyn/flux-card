from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass
from io import TextIOWrapper
from pathlib import Path
import sys
from typing import Any, Dict, Generator, List, cast

from output_registry import FormatterProtocol
from segments import Segment


@dataclass(frozen=True)
class OutputRunner(ABC):
    format_key: str 
    format_function: FormatterProtocol
    kwargs: Dict[str,Any]
    
    def execute_output(self, data: List[Segment]) -> None:
        """Runs the output formatter function
        Expects input data to be sorted by inTime"""

        with self.open_stream() as stream:
            self.format_function(stream,data,**self.kwargs)
            

    @abstractmethod
    @contextmanager
    def open_stream(self) -> Generator[TextIOWrapper,None,None]: ...

    @abstractmethod
    def output_str(self) -> str: ...



@dataclass(frozen=True)
class StdoutRunner(OutputRunner):

    @contextmanager
    def open_stream(self) -> Generator[TextIOWrapper,None,None]:
        yield cast(TextIOWrapper,sys.stdout)

    def output_str(self) -> str:
        return 'stdout'

@dataclass(frozen=True)
class FileRunner(OutputRunner):
    file_path: Path

    @contextmanager
    def open_stream(self) -> Generator[TextIOWrapper,None,None]:
        with self.file_path.open("w") as f:
            yield f

    def output_str(self) -> str:
        return str(self.file_path)
