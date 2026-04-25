from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

from code_sprawl.models import ScanStats, WorldNode, WorldScope
from code_sprawl.ui import app as app_module
from code_sprawl.ui.app import CodeSprawlApp


def _world(root: Path, scope: Path, nodes: list[WorldNode] | None = None) -> WorldScope:
    return WorldScope(
        root=root,
        scope=scope,
        nodes=nodes or [],
        scanned_at=datetime.now(),
        scan_stats=ScanStats(),
    )


def test_load_scope_async_uses_cache(monkeypatch, tmp_path: Path) -> None:
    app = CodeSprawlApp(tmp_path)
    app._fit_camera_to_world = lambda: None
    app._render_world = lambda: None

    calls = {"count": 0}

    def fake_scan_world_scope(
        root_path: str | Path,
        *,
        scope_path: str | Path | None = None,
        include_files: bool = True,
        max_nodes: int = 220,
    ) -> WorldScope:
        del root_path, include_files, max_nodes
        calls["count"] += 1
        scope = Path(scope_path) if scope_path is not None else tmp_path
        return _world(tmp_path, scope, [])

    monkeypatch.setattr(app_module, "scan_world_scope", fake_scan_world_scope)

    asyncio.run(app._load_scope_async(tmp_path))
    asyncio.run(app._load_scope_async(tmp_path))

    assert calls["count"] == 1
    assert (tmp_path.resolve(), False) in app._scope_cache


def test_load_scope_async_selects_first_node(monkeypatch, tmp_path: Path) -> None:
    app = CodeSprawlApp(tmp_path)
    app._fit_camera_to_world = lambda: None
    app._render_world = lambda: None

    node = WorldNode(
        id="pkg",
        name="pkg",
        path=tmp_path / "pkg",
        is_dir=True,
        x=0.0,
        y=0.0,
        radius=3.0,
    )

    def fake_scan_world_scope(
        root_path: str | Path,
        *,
        scope_path: str | Path | None = None,
        include_files: bool = True,
        max_nodes: int = 220,
    ) -> WorldScope:
        del root_path, include_files, max_nodes
        scope = Path(scope_path) if scope_path is not None else tmp_path
        return _world(tmp_path, scope, [node])

    monkeypatch.setattr(app_module, "scan_world_scope", fake_scan_world_scope)

    asyncio.run(app._load_scope_async(tmp_path))

    assert app._selected_id == "pkg"


def test_action_reload_clears_cache_and_starts_worker(tmp_path: Path) -> None:
    app = CodeSprawlApp(tmp_path)
    app._scope_cache[(tmp_path.resolve(), False)] = _world(tmp_path, tmp_path)

    seen: dict[str, object] = {}

    def fake_set_hud(text: str) -> None:
        seen["hud"] = text

    def fake_run_worker(coro: object, exclusive: bool = False) -> None:
        seen["exclusive"] = exclusive
        if hasattr(coro, "close"):
            coro.close()

    app._set_hud = fake_set_hud
    app.run_worker = fake_run_worker  # type: ignore[method-assign]

    app.action_reload()

    assert app._scope_cache == {}
    assert seen["hud"] == "Rescanning world"
    assert seen["exclusive"] is True


def test_action_drill_or_open_directory_pushes_scope_and_starts_worker(tmp_path: Path) -> None:
    app = CodeSprawlApp(tmp_path)
    dir_node = WorldNode(
        id="sub",
        name="sub",
        path=tmp_path / "sub",
        is_dir=True,
        x=0.0,
        y=0.0,
        radius=3.0,
    )
    app._world = _world(tmp_path, tmp_path, [dir_node])
    app._selected_id = "sub"

    seen: dict[str, object] = {}

    def fake_set_hud(text: str) -> None:
        seen["hud"] = text

    def fake_run_worker(coro: object, exclusive: bool = False) -> None:
        seen["exclusive"] = exclusive
        if hasattr(coro, "close"):
            coro.close()

    app._set_hud = fake_set_hud
    app.run_worker = fake_run_worker  # type: ignore[method-assign]

    app.action_drill_or_open()

    assert app.scope_stack == [tmp_path]
    assert seen["hud"] == "Entering sub..."
    assert seen["exclusive"] is True


def test_action_drill_or_open_file_sets_inspector_message(tmp_path: Path) -> None:
    app = CodeSprawlApp(tmp_path)
    file_node = WorldNode(
        id="a.py",
        name="a.py",
        path=tmp_path / "a.py",
        is_dir=False,
        x=0.0,
        y=0.0,
        radius=1.2,
        loc=10,
        complexity=2.0,
        commit_count=1,
        todo_count=0,
    )
    app._world = _world(tmp_path, tmp_path, [file_node])
    app._selected_id = "a.py"

    seen: dict[str, str] = {}

    def fake_set_inspector(title: str, body: str) -> None:
        seen["title"] = title
        seen["body"] = body

    app._set_inspector = fake_set_inspector

    app.action_drill_or_open()

    assert seen["title"] == "a.py"
    assert "FILE OPEN TARGET" in seen["body"]
    assert str(tmp_path / "a.py") in seen["body"]


def test_action_go_back_scope_starts_worker(tmp_path: Path) -> None:
    app = CodeSprawlApp(tmp_path)
    previous = tmp_path / "previous"
    app.scope_stack = [previous]

    seen: dict[str, object] = {}

    def fake_set_hud(text: str) -> None:
        seen["hud"] = text

    def fake_run_worker(coro: object, exclusive: bool = False) -> None:
        seen["exclusive"] = exclusive
        if hasattr(coro, "close"):
            coro.close()

    app._set_hud = fake_set_hud
    app.run_worker = fake_run_worker  # type: ignore[method-assign]

    app.action_go_back_scope()

    assert app.scope_stack == []
    assert seen["hud"] == "Returning to previous..."
    assert seen["exclusive"] is True
