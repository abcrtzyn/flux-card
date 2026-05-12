
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
import tomllib
from typing import Any, Dict, cast

REPO_ROOT = Path(__file__).resolve().parent.parent



@dataclass(frozen=True)
class JobConfig:
    period_anchor: date | None = field(default=None)
    period_length: int | None = field(default=None)

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "JobConfig":
        anchor = raw.get("period_anchor")
        if not isinstance(anchor,date):
            print(f"period_anchor must be a date in YYYY-MM-DD format, got '{anchor}'")
            exit(1)
        length = raw.get("period_length")
        if not isinstance(length,int):
            print(f"period_anchor must be a date in YYYY-MM-DD format, got '{anchor}'")
            exit(1)

        return cls(period_anchor=anchor,period_length=length)

@dataclass(frozen=True)
class AppConfig:
    timecard_path: Path | None = field(default=None)
    output_timezone: str | None = field(default=None)
    default_job: str | None = field(default=None)
    jobs: Dict[str, JobConfig] = cast(Dict[str, JobConfig],field(default_factory=dict))
    
    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "AppConfig":
        if "timecard_path" in raw:
            p = Path(raw["timecard_path"]).expanduser()
            if p.is_absolute():
                timecard_path = p
            else:
                timecard_path = (REPO_ROOT / p).resolve()
        else:
            timecard_path = None
        
        jobs: Dict[str,JobConfig] = {}
        for name, value in raw.get("jobs", {}).items():
            jobs[name] = JobConfig.from_dict(value)
        
        return cls(
            timecard_path=timecard_path,
            output_timezone = raw.get("output_timezone"),
            default_job=raw.get("default_job"),
            jobs=jobs
        )

    @classmethod
    def load(cls, path: Path) -> "AppConfig":
        with path.open("rb") as f:
            raw = tomllib.load(f)
        return cls.from_dict(raw)

    def job_config(self, job_name: str | None) -> JobConfig:
        if job_name is None:
            return JobConfig()
        # if the job is not listed in the config, return a blank one as well
        return self.jobs.get(job_name, JobConfig())
