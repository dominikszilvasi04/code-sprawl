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
