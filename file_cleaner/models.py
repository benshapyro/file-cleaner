from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

Recommendation = Literal["keep", "organize", "review", "quarantine"]
Action = Literal["organize", "quarantine"]


@dataclass
class FileSnapshot:
    path: Path
    root: Path
    size: int
    mtime_ns: int
    mode: int
    age_days: int
    extension: str
    sha256: str | None = None
    category: str = "unknown"
    recommendation: Recommendation = "keep"
    reason: str = "Unknown files are kept by default."
    exact_duplicate_of: Path | None = None
    similar_names: list[Path] = field(default_factory=list)
    ai_note: str | None = None

    @property
    def relative_path(self) -> Path:
        return self.path.relative_to(self.root)

    def public_dict(self) -> dict:
        value = asdict(self)
        for key in ("path", "root", "exact_duplicate_of"):
            if value[key] is not None:
                value[key] = str(value[key])
        value["similar_names"] = [str(path) for path in self.similar_names]
        return value


@dataclass(frozen=True)
class PlannedAction:
    snapshot: FileSnapshot
    action: Action
    destination_group: str | None = None


@dataclass
class ActionResult:
    action: str
    source: str
    destination: str | None
    status: Literal["succeeded", "skipped", "failed", "restored", "purged"]
    reason: str
    size: int
    sha256: str | None = None
