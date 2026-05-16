"""This file contains classes that give parse the config dictionary and make nice easily type-checkable classes."""



from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date
from io import TextIOWrapper
from pathlib import Path
import sys
import tomllib
from typing import Any, Dict, Generator, List, cast
from zoneinfo import ZoneInfo

from error import FluxCardInputError

REPO_ROOT = Path(__file__).resolve().parent.parent

def resolve_config_relative_path(raw_path: str, config_file: Path) -> Path:
    """
    Normalizes a path string from TOML. 
    Absolute paths stay absolute. Relative paths anchor to the config file's directory.
    """
    p = Path(raw_path).expanduser()
    if p.is_absolute():
        return p
    return (config_file.parent / p).resolve()


@dataclass(frozen=True)
class JobConfig:
    period_anchor: date | None = field(default=None)
    period_length: int | None = field(default=None)

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "JobConfig":
        anchor = raw.get("period_anchor")
        if anchor is not None and not isinstance(anchor,date):
            raise FluxCardInputError(f"period_anchor must be a date in YYYY-MM-DD format, got '{anchor}'")
            
        length = raw.get("period_length")
        if length is not None and not isinstance(length,int):
            raise FluxCardInputError(f"period_anchor must be a date in YYYY-MM-DD format, got '{anchor}'")

        return cls(period_anchor=anchor,period_length=length)

@dataclass(frozen=True)
class OutputConfig(ABC):
    # path to a file or stdout if none
    output_format: str
    is_stdout: bool
    
    @abstractmethod
    @contextmanager
    def open_stream(self) -> Generator[TextIOWrapper,None,None]: ...


    @classmethod
    def from_dict(cls, raw: Dict[str,Any], config_path: Path) -> "OutputConfig":
        # output is required, otherwise, how would we know how to output?
        form = raw.get("format")
        if not isinstance(form,str):
            raise FluxCardInputError(f"format must be a string. Got '{form}'")
        
        # destination can be None or stdout for stdout
        if "dest" not in raw or raw["dest"] == "stdout":
            return StdoutConfig(output_format=form)

        dest_file_path = resolve_config_relative_path(raw["dest"], config_path)
        
        return FileConfig(form,dest_file_path)

@dataclass(frozen=True)
class StdoutConfig(OutputConfig):
    is_stdout: bool = field(default=True,init=False,repr=False)

    @contextmanager
    def open_stream(self) -> Generator[TextIOWrapper,None,None]:
        yield cast(TextIOWrapper,sys.stdout)


@dataclass(frozen=True)
class FileConfig(OutputConfig):
    file_path: Path
    is_stdout: bool = field(default=False,init=False,repr=False)

    @contextmanager
    def open_stream(self) -> Generator[TextIOWrapper,None,None]:
        with self.file_path.open("w") as f:
            yield f

@dataclass(frozen=True)
class MacroConfig:
    job_filter: str | None #= field(default=None)
    period: int | None #= field(default=None)
    outputs: List[OutputConfig] #= cast(List[OutputConfig],field(default_factory=list))

    @classmethod
    def from_dict(cls, raw: Dict[str,Any], config_path: Path) -> "MacroConfig":
        

        job_filter = raw.get('job_filter')
        if job_filter is not None and not isinstance(job_filter,str):
            raise FluxCardInputError(f"job filter must be a string. Got '{job_filter}'")

        period = raw.get('period')
        if period is not None and not isinstance(period,int):
            raise FluxCardInputError(f"period must be an int. Got '{period}'")
        
        outputs: List[OutputConfig] = []
        for index, value in enumerate(raw.get('outputs', [])):
            try:
                outputs.append(OutputConfig.from_dict(value,config_path))
            except Exception as e:
                e.add_note(f'in outputs index {index} (0 based)')
                raise e

        return cls(job_filter,period,outputs)


@dataclass(frozen=True)
class AppConfig:
    timecard_path: Path | None = field(default=None)
    output_timezone: ZoneInfo | None = field(default=None)
    default_job: str | None = field(default=None)
    jobs: Dict[str, JobConfig] = cast(Dict[str, JobConfig],field(default_factory=dict))
    macros: Dict[str, MacroConfig] = cast(Dict[str, MacroConfig], field(default_factory=dict))
    
    @classmethod
    def from_dict(cls, raw: Dict[str, Any], config_path: Path) -> "AppConfig":
        timecard_path = resolve_config_relative_path(raw["timecard_path"], config_path) if "timecard_path" in raw else None
        
        output_timezone_str = cast(str|None,raw.get("output_timezone"))
        output_timezone = ZoneInfo(output_timezone_str) if output_timezone_str else None

        jobs: Dict[str,JobConfig] = {}
        for name, value in raw.get("jobs", {}).items():
            try:
                jobs[name] = JobConfig.from_dict(value)
            except Exception as e:
                e.add_note(f'in job config {name}')
                raise e

        macros: Dict[str,MacroConfig] = {}
        for name, value in raw.get("macros", {}).items():
            try:
                macros[name] = MacroConfig.from_dict(value,config_path)
            except Exception as e:
                e.add_note(f'in macro {name}')
                raise e
        
        return cls(
            timecard_path=timecard_path,
            output_timezone = output_timezone,
            default_job=raw.get("default_job"),
            jobs=jobs,
            macros=macros
        )

    @classmethod
    def load(cls, path: Path) -> "AppConfig":
        with path.open("rb") as f:
            raw = tomllib.load(f)
        return cls.from_dict(raw, path)

    def job_config(self, job_name: str | None) -> JobConfig:
        if job_name is None:
            return JobConfig()
        # if the job is not listed in the config, return a blank one as well
        return self.jobs.get(job_name, JobConfig())
