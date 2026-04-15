from __future__ import annotations

import os
from collections import Counter
from datetime import datetime
from pathlib import Path

from pathspec import PathSpec
from pydriller import Repository
from radon.complexity import cc_visit

from .models import Building, CitySnapshot, District

_SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", "dist", "build"}
_TEXT_EXTENSIONS = {
    ".py", ".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg",
    ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".scss", ".sql", ".sh", ".ps1",
}


def _load_gitignore_spec(root: Path) -> PathSpec | None:
    patterns: list[str] = []

    for ignore_file in root.rglob(".gitignore"):
        if ".git" in ignore_file.parts:
            continue

        try:
            lines = ignore_file.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue

        parent_rel = ignore_file.parent.relative_to(root).as_posix()

        for raw in lines:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue

            is_negated = line.startswith("!")
            if is_negated:
                line = line[1:]

            is_anchored = line.startswith("/")
            if is_anchored:
                line = line[1:]

            if not line:
                continue

            if parent_rel != ".":
                line = f"{parent_rel}/{line}"

            if is_negated:
                line = f"!{line}"

            patterns.append(line)

    if not patterns:
        return None

    return PathSpec.from_lines("gitwildmatch", patterns)


def _is_gitignored(root: Path, path: Path, spec: PathSpec | None, *, is_dir: bool = False) -> bool:
    if spec is None:
        return False

    rel = path.relative_to(root).as_posix()
    if is_dir:
        return spec.match_file(rel) or spec.match_file(f"{rel}/")
    return spec.match_file(rel)


def _is_text_file(path: Path) -> bool:
    if path.suffix.lower() in _TEXT_EXTENSIONS:
        return True
    try:
        with path.open("rb") as f:
            chunk = f.read(2048)
        return b"\0" not in chunk
    except OSError:
        return False


def _count_loc(path: Path) -> int:
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


def _count_todos(path: Path) -> int:
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            text = f.read().lower()
        return text.count("todo")
    except OSError:
        return 0


def _complexity_for_python(path: Path) -> float:
    if path.suffix.lower() != ".py":
        return 0.0
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            blocks = cc_visit(f.read())
        if not blocks:
            return 0.0
        return max(float(block.complexity) for block in blocks)
    except Exception:
        return 0.0


def _collect_commit_heat(root: Path, max_commits: int = 600) -> Counter[str]:
    heat: Counter[str] = Counter()
    try:
        for idx, commit in enumerate(Repository(str(root)).traverse_commits()):
            if idx >= max_commits:
                break
            for modified in commit.modified_files:
                changed_path = modified.new_path or modified.old_path
                if changed_path:
                    normalized = changed_path.replace("\\", "/")
                    heat[normalized] += 1
    except Exception:
        return Counter()
    return heat


def scan_repository(root_path: str | Path) -> CitySnapshot:
    root = Path(root_path).resolve()
    now = datetime.now()
    commit_heat = _collect_commit_heat(root)
    gitignore_spec = _load_gitignore_spec(root)

    district_map: dict[str, District] = {}
    total_todos = 0

    for current_root, dirs, files in os.walk(root):
        current_path = Path(current_root)

        dirs[:] = [
            d
            for d in dirs
            if d not in _SKIP_DIRS and not _is_gitignored(root, current_path / d, gitignore_spec, is_dir=True)
        ]

        rel_dir = current_path.relative_to(root)
        district_key = str(rel_dir) if str(rel_dir) != "." else "root"

        buildings: list[Building] = []
        for file_name in files:
            full_path = current_path / file_name
            if _is_gitignored(root, full_path, gitignore_spec):
                continue
            if not _is_text_file(full_path):
                continue

            stat = full_path.stat()
            age_days = max(0, int((now.timestamp() - stat.st_mtime) // 86400))
            loc = _count_loc(full_path)
            todo_count = _count_todos(full_path)
            complexity = _complexity_for_python(full_path)

            rel_file = full_path.relative_to(root).as_posix()
            commits = commit_heat.get(rel_file, 0)

            building = Building(
                path=full_path,
                name=file_name,
                extension=full_path.suffix.lower() or "(none)",
                loc=loc,
                age_days=age_days,
                modified_ts=stat.st_mtime,
                commit_count=commits,
                complexity=complexity,
                todo_count=todo_count,
            )
            buildings.append(building)
            total_todos += todo_count

        if buildings:
            buildings.sort(key=lambda b: (b.loc, b.commit_count), reverse=True)
            district_map[district_key] = District(name=district_key, path=current_path, buildings=buildings)

    districts = sorted(district_map.values(), key=lambda d: len(d.buildings), reverse=True)
    return CitySnapshot(root=root, districts=districts, scanned_at=now, todo_count=total_todos)
