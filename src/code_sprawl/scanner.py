from __future__ import annotations

import os
from hashlib import sha1
from math import cos, pi, sin, sqrt
from collections import Counter
from datetime import datetime
from pathlib import Path

from pathspec import PathSpec
from pydriller import Repository
from radon.complexity import cc_visit

from .models import Building, CitySnapshot, District, ScanStats, WorldNode, WorldScope

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


def scan_repository(root_path: str | Path, *, include_empty_districts: bool = True) -> CitySnapshot:
    root = Path(root_path).resolve()
    now = datetime.now()
    commit_heat = _collect_commit_heat(root)
    gitignore_spec = _load_gitignore_spec(root)

    district_map: dict[str, District] = {}
    total_todos = 0
    stats = ScanStats()

    for current_root, dirs, files in os.walk(root):
        stats.dirs_seen += 1
        current_path = Path(current_root)

        original_dirs = list(dirs)
        skipped_builtin = 0
        skipped_gitignore = 0

        filtered_dirs: list[str] = []
        for d in original_dirs:
            dir_path = current_path / d
            if d in _SKIP_DIRS:
                skipped_builtin += 1
                continue
            if _is_gitignored(root, dir_path, gitignore_spec, is_dir=True):
                skipped_gitignore += 1
                continue
            filtered_dirs.append(d)

        dirs[:] = filtered_dirs
        stats.dirs_skipped_builtin += skipped_builtin
        stats.dirs_skipped_gitignore += skipped_gitignore

        rel_dir = current_path.relative_to(root)
        district_key = str(rel_dir) if str(rel_dir) != "." else "root"

        buildings: list[Building] = []
        for file_name in files:
            stats.files_seen += 1
            full_path = current_path / file_name
            if _is_gitignored(root, full_path, gitignore_spec):
                stats.files_skipped_gitignore += 1
                continue
            if not _is_text_file(full_path):
                stats.files_skipped_non_text += 1
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
            stats.files_included += 1

        if buildings:
            buildings.sort(key=lambda b: (b.loc, b.commit_count), reverse=True)
            district_map[district_key] = District(name=district_key, path=current_path, buildings=buildings)
        elif include_empty_districts:
            district_map[district_key] = District(name=district_key, path=current_path, buildings=[])

    districts = sorted(district_map.values(), key=lambda d: (len(d.buildings), d.name), reverse=True)
    return CitySnapshot(
        root=root,
        districts=districts,
        scanned_at=now,
        todo_count=total_todos,
        scan_stats=stats,
    )


def _hash_unit(value: str) -> float:
    digest = sha1(value.encode("utf-8", errors="ignore")).digest()
    integer = int.from_bytes(digest[:8], "big")
    return integer / float(2**64 - 1)


def _aggregate_directory_metrics(
    root: Path,
    directory: Path,
    gitignore_spec: PathSpec | None,
    commit_heat: Counter[str],
    *,
    max_files: int = 800,
) -> tuple[int, int, int, float, int]:
    loc = 0
    todos = 0
    commits = 0
    complexity = 0.0
    file_count = 0

    for current_root, dirs, files in os.walk(directory):
        current = Path(current_root)
        dirs[:] = [
            d
            for d in dirs
            if d not in _SKIP_DIRS and not _is_gitignored(root, current / d, gitignore_spec, is_dir=True)
        ]

        for file_name in files:
            full_path = current / file_name
            if _is_gitignored(root, full_path, gitignore_spec):
                continue
            if not _is_text_file(full_path):
                continue

            rel_file = full_path.relative_to(root).as_posix()
            loc += _count_loc(full_path)
            todos += _count_todos(full_path)
            complexity = max(complexity, _complexity_for_python(full_path))
            commits += commit_heat.get(rel_file, 0)
            file_count += 1

            if file_count >= max_files:
                return loc, todos, commits, complexity, file_count

    return loc, todos, commits, complexity, file_count


def _layout_world_nodes(scope: Path, nodes: list[WorldNode]) -> list[WorldNode]:
    if not nodes:
        return []

    positioned: list[WorldNode] = []
    count = len(nodes)
    base_ring = max(10.0, sqrt(count) * 5.0)

    for index, node in enumerate(sorted(nodes, key=lambda n: (not n.is_dir, -n.radius, n.name.lower()))):
        seed = _hash_unit(f"{scope.as_posix()}::{node.path.as_posix()}")
        angle = ((index / max(1, count)) * (2 * pi)) + (seed * 0.45)
        ring = base_ring + (index // 12) * 8.0 + (seed * 2.0)
        wobble = (_hash_unit(node.id + "w") - 0.5) * 3.5

        x = cos(angle) * (ring + wobble)
        y = sin(angle) * (ring + wobble * 0.6)

        positioned.append(
            WorldNode(
                id=node.id,
                name=node.name,
                path=node.path,
                is_dir=node.is_dir,
                x=x,
                y=y,
                radius=node.radius,
                extension=node.extension,
                loc=node.loc,
                age_days=node.age_days,
                commit_count=node.commit_count,
                complexity=node.complexity,
                todo_count=node.todo_count,
                child_count=node.child_count,
            )
        )

    return positioned


def scan_world_scope(
    root_path: str | Path,
    *,
    scope_path: str | Path | None = None,
    include_files: bool = True,
    max_nodes: int = 220,
) -> WorldScope:
    root = Path(root_path).resolve()
    scope = Path(scope_path).resolve() if scope_path is not None else root
    now = datetime.now()

    gitignore_spec = _load_gitignore_spec(root)
    commit_heat = _collect_commit_heat(root)
    stats = ScanStats()

    if not scope.exists() or not scope.is_dir() or root not in scope.parents and scope != root:
        return WorldScope(root=root, scope=root, nodes=[], scanned_at=now, scan_stats=stats)

    nodes: list[WorldNode] = []

    entries = []
    try:
        entries = list(scope.iterdir())
    except OSError:
        entries = []

    for entry in entries:
        stats.files_seen += 1

        if entry.name in _SKIP_DIRS:
            if entry.is_dir():
                stats.dirs_skipped_builtin += 1
            else:
                stats.files_skipped_non_text += 1
            continue

        if _is_gitignored(root, entry, gitignore_spec, is_dir=entry.is_dir()):
            if entry.is_dir():
                stats.dirs_skipped_gitignore += 1
            else:
                stats.files_skipped_gitignore += 1
            continue

        if entry.is_dir():
            loc, todos, commits, complexity, file_count = _aggregate_directory_metrics(
                root,
                entry,
                gitignore_spec,
                commit_heat,
            )
            child_count = 0
            try:
                child_count = sum(1 for _ in entry.iterdir())
            except OSError:
                child_count = file_count

            radius = max(3.0, min(9.0, 3.0 + sqrt(max(1, file_count)) * 0.45))
            nodes.append(
                WorldNode(
                    id=entry.relative_to(root).as_posix(),
                    name=entry.name,
                    path=entry,
                    is_dir=True,
                    x=0.0,
                    y=0.0,
                    radius=radius,
                    loc=loc,
                    age_days=0,
                    commit_count=commits,
                    complexity=complexity,
                    todo_count=todos,
                    child_count=child_count,
                )
            )
            stats.dirs_seen += 1
            continue

        if not include_files:
            continue
        if not _is_text_file(entry):
            stats.files_skipped_non_text += 1
            continue

        try:
            entry_stat = entry.stat()
        except OSError:
            continue

        loc = _count_loc(entry)
        todos = _count_todos(entry)
        complexity = _complexity_for_python(entry)
        age_days = max(0, int((now.timestamp() - entry_stat.st_mtime) // 86400))
        rel_file = entry.relative_to(root).as_posix()
        commits = commit_heat.get(rel_file, 0)
        radius = max(1.2, min(3.6, 1.2 + (loc / 600)))

        nodes.append(
            WorldNode(
                id=rel_file,
                name=entry.name,
                path=entry,
                is_dir=False,
                x=0.0,
                y=0.0,
                radius=radius,
                extension=entry.suffix.lower(),
                loc=loc,
                age_days=age_days,
                commit_count=commits,
                complexity=complexity,
                todo_count=todos,
                child_count=0,
            )
        )
        stats.files_included += 1

    nodes.sort(key=lambda n: (n.is_dir, n.radius, n.commit_count, n.loc), reverse=True)
    nodes = nodes[:max_nodes]
    positioned = _layout_world_nodes(scope, nodes)

    return WorldScope(
        root=root,
        scope=scope,
        nodes=positioned,
        scanned_at=now,
        scan_stats=stats,
    )
