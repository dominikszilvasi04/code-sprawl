from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass(slots=True)
class Building:
    path: Path
    name: str
    extension: str
    loc: int
    age_days: int
    modified_ts: float
    commit_count: int = 0
    complexity: float = 0.0
    todo_count: int = 0

    @property
    def height(self) -> int:
        return max(1, min(12, self.loc // 20 + 1))

    @property
    def debt_level(self) -> str:
        if self.complexity >= 15:
            return "critical"
        if self.complexity >= 8:
            return "high"
        if self.complexity >= 4:
            return "medium"
        return "low"


@dataclass(slots=True)
class District:
    name: str
    path: Path
    buildings: list[Building] = field(default_factory=list)


@dataclass(slots=True)
class ScanStats:
    dirs_seen: int = 0
    dirs_skipped_builtin: int = 0
    dirs_skipped_gitignore: int = 0
    files_seen: int = 0
    files_included: int = 0
    files_skipped_gitignore: int = 0
    files_skipped_non_text: int = 0


@dataclass(slots=True)
class CitySnapshot:
    root: Path
    districts: list[District]
    scanned_at: datetime
    todo_count: int = 0
    scan_stats: ScanStats = field(default_factory=ScanStats)


@dataclass(slots=True)
class WorldNode:
    id: str
    name: str
    path: Path
    is_dir: bool
    x: float
    y: float
    radius: float
    extension: str = ""
    loc: int = 0
    age_days: int = 0
    commit_count: int = 0
    complexity: float = 0.0
    todo_count: int = 0
    child_count: int = 0

    @property
    def debt_level(self) -> str:
        if self.complexity >= 15:
            return "critical"
        if self.complexity >= 8:
            return "high"
        if self.complexity >= 4:
            return "medium"
        return "low"


@dataclass(slots=True)
class WorldScope:
    root: Path
    scope: Path
    nodes: list[WorldNode]
    scanned_at: datetime
    scan_stats: ScanStats = field(default_factory=ScanStats)
