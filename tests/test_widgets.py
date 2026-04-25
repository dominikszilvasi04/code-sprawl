from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from rich.text import Text

from code_sprawl.models import ScanStats, WorldNode, WorldScope
from code_sprawl.ui.widgets import WorldViewport


def _scope(tmp_path: Path, nodes: list[WorldNode]) -> WorldScope:
    return WorldScope(
        root=tmp_path,
        scope=tmp_path,
        nodes=nodes,
        scanned_at=datetime.now(),
        scan_stats=ScanStats(),
    )


def test_pick_node_prefers_nearest(tmp_path: Path) -> None:
    viewport = WorldViewport()
    near = WorldNode(
        id="near", name="near", path=tmp_path / "near", is_dir=True, x=1.0, y=1.0, radius=2.5
    )
    far = WorldNode(
        id="far", name="far", path=tmp_path / "far", is_dir=True, x=9.0, y=9.0, radius=2.5
    )
    viewport.scope = _scope(tmp_path, [far, near])

    chosen = viewport._pick_node(1.1, 1.2)

    assert chosen is not None
    assert chosen.id == "near"


def test_on_click_posts_focus_and_activation(tmp_path: Path) -> None:
    viewport = WorldViewport()
    node = WorldNode(
        id="a", name="alpha", path=tmp_path / "a", is_dir=True, x=0.0, y=0.0, radius=3.0
    )
    viewport.scope = _scope(tmp_path, [node])
    viewport.zoom = 1.0
    viewport.camera_x = 0.0
    viewport.camera_y = 0.0

    posted: list[object] = []
    viewport.post_message = lambda message: posted.append(message)  # type: ignore[assignment]

    click = SimpleNamespace(x=0, y=0, chain=1)
    viewport.on_click(click)
    viewport.on_click(click)

    assert len(posted) >= 3
    assert any(isinstance(msg, WorldViewport.NodeFocused) for msg in posted)
    assert any(isinstance(msg, WorldViewport.NodeActivated) for msg in posted)


def test_render_returns_text_with_scope(tmp_path: Path) -> None:
    viewport = WorldViewport()
    d = WorldNode(
        id="dir", name="directory", path=tmp_path / "dir", is_dir=True, x=0.0, y=0.0, radius=3.5
    )
    f = WorldNode(
        id="file.py",
        name="file.py",
        path=tmp_path / "file.py",
        is_dir=False,
        x=5.0,
        y=2.0,
        radius=1.4,
        extension=".py",
        complexity=9.0,
        commit_count=15,
    )
    viewport.set_world(_scope(tmp_path, [d, f]))
    viewport.set_selected("dir")
    viewport.set_camera(0.0, 0.0, 1.0)

    rendered = viewport.render()

    assert isinstance(rendered, Text)
    assert rendered.plain


def test_draw_inner_label_handles_zoom_and_small_radius(tmp_path: Path) -> None:
    viewport = WorldViewport()
    viewport.zoom = 1.8

    row = [" " for _ in range(80)]
    buffer = [row.copy() for _ in range(5)]
    spans: list[tuple[int, int, int, str]] = []

    node = WorldNode(
        id="pkg",
        name="very_long_package_name",
        path=tmp_path / "pkg",
        is_dir=True,
        x=0.0,
        y=0.0,
        radius=1.3,
        complexity=16.0,
    )

    viewport._draw_inner_label(buffer, 20, 2, 1, node.name, node, spans)

    assert spans
    line, start, end, style = spans[0]
    assert line == 2
    assert end > start
    assert "magenta" in style


def test_selected_node_returns_matching_item(tmp_path: Path) -> None:
    viewport = WorldViewport()
    one = WorldNode(
        id="one", name="one", path=tmp_path / "one", is_dir=True, x=0.0, y=0.0, radius=2.0
    )
    two = WorldNode(
        id="two", name="two", path=tmp_path / "two", is_dir=True, x=0.0, y=0.0, radius=2.0
    )
    viewport.scope = _scope(tmp_path, [one, two])
    viewport.selected_id = "two"

    selected = viewport.selected_node()

    assert selected is not None
    assert selected.id == "two"
