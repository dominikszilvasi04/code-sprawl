from __future__ import annotations

from pathlib import Path

from code_sprawl.scanner import scan_repository, scan_world_scope


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_scan_repository_respects_gitignore(tmp_path: Path) -> None:
    _write(tmp_path / ".gitignore", "ignored_dir/\n*.log\n")
    _write(tmp_path / "src" / "main.py", "print('hello')\n")
    _write(tmp_path / "ignored_dir" / "secret.py", "print('x')\n")
    _write(tmp_path / "notes.log", "skip me\n")

    snapshot = scan_repository(tmp_path, include_empty_districts=True)

    district_names = {d.name for d in snapshot.districts}
    assert "src" in district_names
    assert "ignored_dir" not in district_names
    assert snapshot.scan_stats.files_skipped_gitignore >= 1


def test_scan_world_scope_builds_directory_and_file_nodes(tmp_path: Path) -> None:
    _write(tmp_path / "api" / "handler.py", "def f():\n    return 1\n")
    _write(tmp_path / "README.md", "# hi\n")

    world = scan_world_scope(tmp_path, scope_path=tmp_path, include_files=True, max_nodes=200)

    assert world.scope == tmp_path
    assert len(world.nodes) >= 2

    names = {node.name for node in world.nodes}
    assert "api" in names
    assert "README.md" in names

    directory_nodes = [n for n in world.nodes if n.is_dir]
    file_nodes = [n for n in world.nodes if not n.is_dir]
    assert directory_nodes
    assert file_nodes


def test_world_nodes_have_reasonable_spread(tmp_path: Path) -> None:
    for idx in range(8):
        _write(tmp_path / f"dir_{idx}" / "main.py", f"print({idx})\n")

    world = scan_world_scope(tmp_path, scope_path=tmp_path, include_files=False, max_nodes=200)

    xs = [n.x for n in world.nodes]
    ys = [n.y for n in world.nodes]
    assert xs and ys
    assert max(xs) - min(xs) > 10
    assert max(ys) - min(ys) > 10


def test_scan_world_scope_excludes_files_when_requested(tmp_path: Path) -> None:
    _write(tmp_path / "pkg" / "mod.py", "def run():\n    return 1\n")
    _write(tmp_path / "README.md", "# docs\n")

    world = scan_world_scope(tmp_path, scope_path=tmp_path, include_files=False, max_nodes=200)

    assert world.nodes
    assert all(node.is_dir for node in world.nodes)


def test_scan_world_scope_invalid_scope_returns_empty_root_scope(tmp_path: Path) -> None:
    _write(tmp_path / "a.py", "print('ok')\n")
    invalid_scope = tmp_path / "missing"

    world = scan_world_scope(tmp_path, scope_path=invalid_scope, include_files=True, max_nodes=50)

    assert world.root == tmp_path
    assert world.scope == tmp_path
    assert world.nodes == []


def test_scan_world_scope_respects_max_nodes(tmp_path: Path) -> None:
    for idx in range(15):
        _write(tmp_path / f"f_{idx}.py", f"print({idx})\n")

    world = scan_world_scope(tmp_path, scope_path=tmp_path, include_files=True, max_nodes=5)

    assert len(world.nodes) == 5


def test_scan_world_scope_respects_gitignore_for_nodes(tmp_path: Path) -> None:
    _write(tmp_path / ".gitignore", "ignored.py\nignored_dir/\n")
    _write(tmp_path / "kept.py", "print('kept')\n")
    _write(tmp_path / "ignored.py", "print('ignored')\n")
    _write(tmp_path / "ignored_dir" / "inner.py", "print('ignored dir')\n")

    world = scan_world_scope(tmp_path, scope_path=tmp_path, include_files=True, max_nodes=100)
    names = {node.name for node in world.nodes}

    assert "kept.py" in names
    assert "ignored.py" not in names
    assert "ignored_dir" not in names
    assert world.scan_stats.files_skipped_gitignore >= 1


def test_world_nodes_normalized_to_reasonable_bounds(tmp_path: Path) -> None:
    for idx in range(22):
        _write(tmp_path / f"dir_{idx}" / "main.py", "def f():\n    return 1\n")

    world = scan_world_scope(tmp_path, scope_path=tmp_path, include_files=False, max_nodes=220)

    assert world.nodes
    max_extent = max(
        max(abs(node.x) + node.radius, abs(node.y) + node.radius) for node in world.nodes
    )
    assert max_extent <= 102
