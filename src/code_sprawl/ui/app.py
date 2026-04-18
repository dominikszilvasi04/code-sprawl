from __future__ import annotations

import asyncio
from math import sqrt
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Footer, Header, Label, Static

from ..models import WorldNode, WorldScope
from ..scanner import scan_world_scope
from .widgets import WorldViewport


class CodeSprawlApp(App):
    CSS_PATH = "styles.tcss"
    TITLE = "Code-Sprawl"
    SUB_TITLE = "2D Neon World"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "reload", "Rescan"),
        ("up", "pan_up", "Pan Up"),
        ("down", "pan_down", "Pan Down"),
        ("left", "pan_left", "Pan Left"),
        ("right", "pan_right", "Pan Right"),
        ("ctrl+up", "zoom_in", "Zoom In"),
        ("ctrl+down", "zoom_out", "Zoom Out"),
        ("plus", "zoom_in", "Zoom In"),
        ("minus", "zoom_out", "Zoom Out"),
        ("enter", "drill_or_open", "Drill/Open"),
        ("b", "go_back_scope", "Back Scope"),
        ("c", "center_camera", "Center"),
        ("f", "fit_world", "Fit World"),
    ]

    def __init__(self, repo_path: Path) -> None:
        super().__init__()
        self.repo_root = repo_path.resolve()
        self.current_scope = self.repo_root
        self.scope_stack: list[Path] = []

        self._world: WorldScope | None = None
        self._selected_id: str | None = None
        self._camera_x = 0.0
        self._camera_y = 0.0
        self._zoom = 1.0

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label("CODE-SPRAWL // WORLD MODE // arrows pan // ctrl+up/down zoom // enter drill", id="banner")
        with Horizontal(id="main-layout"):
            yield WorldViewport()
            yield Static(id="inspector")
        yield Static(id="hud")
        yield Footer()

    def on_mount(self) -> None:
        self._set_inspector("Boot", "Scanning root scope...")
        self._set_hud("Loading world")
        self.run_worker(self._load_scope_async(self.current_scope), exclusive=True)

    async def _load_scope_async(self, scope: Path) -> None:
        world = await asyncio.to_thread(
            scan_world_scope,
            self.repo_root,
            scope_path=scope,
            include_files=True,
            max_nodes=260,
        )

        self._world = world
        self.current_scope = world.scope
        self._camera_x = 0.0
        self._camera_y = 0.0
        self._zoom = 1.0

        if world.nodes:
            self._selected_id = world.nodes[0].id
        else:
            self._selected_id = None

        self._fit_camera_to_world()

        self._render_world()

    def _fit_camera_to_world(self) -> None:
        if self._world is None or not self._world.nodes:
            self._camera_x = 0.0
            self._camera_y = 0.0
            self._zoom = 1.0
            return

        min_x = min(n.x - n.radius for n in self._world.nodes)
        max_x = max(n.x + n.radius for n in self._world.nodes)
        min_y = min(n.y - n.radius for n in self._world.nodes)
        max_y = max(n.y + n.radius for n in self._world.nodes)

        self._camera_x = (min_x + max_x) / 2
        self._camera_y = (min_y + max_y) / 2

        viewport = self.query_one(WorldViewport)
        width = max(24, viewport.size.width)
        height = max(12, viewport.size.height)

        span_x = max(12.0, max_x - min_x)
        span_y = max(8.0, max_y - min_y)

        fit_zoom = min((width - 6) / span_x, (height - 4) / span_y)
        density = sqrt(len(self._world.nodes))
        fit_zoom *= max(0.7, min(1.15, 10.0 / max(4.0, density)))
        self._zoom = max(0.55, min(2.4, fit_zoom))

    def _render_world(self) -> None:
        viewport = self.query_one(WorldViewport)
        if self._world is None:
            return

        viewport.set_world(self._world)
        viewport.set_selected(self._selected_id)
        viewport.set_camera(self._camera_x, self._camera_y, self._zoom)

        selected = self._selected_node()
        if selected is not None:
            self._set_inspector_for_node(selected)
        else:
            self._set_inspector("World", "No node selected")

        self._set_hud(
            f"scope={self.current_scope.relative_to(self.repo_root) if self.current_scope != self.repo_root else '.'}  "
            f"zoom={self._zoom:.2f}  nodes={len(self._world.nodes)}  "
            "controls: arrows pan | ctrl+up/down zoom | enter drill/open | b back | c center"
        )

    def _selected_node(self) -> WorldNode | None:
        if self._world is None or self._selected_id is None:
            return None
        return next((n for n in self._world.nodes if n.id == self._selected_id), None)

    def _set_hud(self, text: str) -> None:
        self.query_one("#hud", Static).update(text)

    def _set_inspector(self, title: str, body: str) -> None:
        self.query_one("#inspector", Static).update(f"[bold cyan]{title}[/]\n\n{body}")

    def _set_inspector_for_node(self, node: WorldNode) -> None:
        kind = "DIR" if node.is_dir else "FILE"
        self._set_inspector(
            node.name,
            (
                f"Type: {kind}\n"
                f"Path: {node.path}\n"
                f"Children: {node.child_count}\n"
                f"LoC: {node.loc}\n"
                f"Commits: {node.commit_count}\n"
                f"Complexity: {node.complexity:.1f} ({node.debt_level})\n"
                f"TODOs: {node.todo_count}\n"
                f"Age: {node.age_days} days\n\n"
                "Interaction:\n"
                "- Click blob/file to select\n"
                "- Double-click or Enter to drill/open\n"
                "- b to go back"
            ),
        )

    def action_reload(self) -> None:
        self.run_worker(self._load_scope_async(self.current_scope), exclusive=True)

    def _pan(self, dx: float, dy: float) -> None:
        step = max(1.5, 5.0 / max(0.45, self._zoom))
        self._camera_x += dx * step
        self._camera_y += dy * step
        self._render_world()

    def action_pan_up(self) -> None:
        self._pan(0, -1)

    def action_pan_down(self) -> None:
        self._pan(0, 1)

    def action_pan_left(self) -> None:
        self._pan(-1, 0)

    def action_pan_right(self) -> None:
        self._pan(1, 0)

    def action_zoom_in(self) -> None:
        self._zoom = min(3.4, self._zoom * 1.15)
        self._render_world()

    def action_zoom_out(self) -> None:
        self._zoom = max(0.45, self._zoom / 1.15)
        self._render_world()

    def action_center_camera(self) -> None:
        self._camera_x = 0.0
        self._camera_y = 0.0
        self._render_world()

    def action_fit_world(self) -> None:
        self._fit_camera_to_world()
        self._render_world()

    def action_drill_or_open(self) -> None:
        node = self._selected_node()
        if node is None:
            return

        if node.is_dir:
            self.scope_stack.append(self.current_scope)
            self.run_worker(self._load_scope_async(node.path), exclusive=True)
            return

        self._set_inspector(
            node.name,
            (
                f"FILE OPEN TARGET\n\n"
                f"Path: {node.path}\n"
                f"LoC: {node.loc}\n"
                f"Complexity: {node.complexity:.1f}\n"
                f"Commits: {node.commit_count}\n"
                f"TODOs: {node.todo_count}\n\n"
                "Next step: integrate direct open in editor command."
            ),
        )

    def action_go_back_scope(self) -> None:
        if not self.scope_stack:
            return
        previous = self.scope_stack.pop()
        self.run_worker(self._load_scope_async(previous), exclusive=True)

    def on_world_viewport_node_focused(self, message: WorldViewport.NodeFocused) -> None:
        if message.node is None:
            return
        self._selected_id = message.node.id
        self._set_inspector_for_node(message.node)

    def on_world_viewport_node_activated(self, message: WorldViewport.NodeActivated) -> None:
        self._selected_id = message.node.id
        self.action_drill_or_open()
