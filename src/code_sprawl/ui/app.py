from __future__ import annotations

import asyncio
from math import sqrt
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
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
        ("tab", "select_next_node", "Next Node"),
        ("shift+tab", "select_prev_node", "Prev Node"),
        ("g", "snap_to_selected", "Snap Camera"),
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
        self._scope_cache: dict[tuple[Path, bool], WorldScope] = {}

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label(
            "CODE-SPRAWL // WORLD MODE // arrows pan // ctrl+up/down zoom // enter drill",
            id="banner",
        )
        with Horizontal(id="main-layout"):
            yield WorldViewport()
            with Vertical(id="right-panel"):
                yield Static(id="inspector")
                yield Static(id="minimap")
        yield Static(id="hud")
        yield Footer()

    def on_mount(self) -> None:
        self._set_inspector("Boot", "Scanning root scope...")
        self._set_hud("Loading world")
        self.run_worker(self._load_scope_async(self.current_scope), exclusive=True)

    async def _load_scope_async(self, scope: Path) -> None:
        include_files = scope != self.repo_root
        cache_key = (scope.resolve(), include_files)
        world = self._scope_cache.get(cache_key)
        if world is None:
            world = await asyncio.to_thread(
                scan_world_scope,
                self.repo_root,
                scope_path=scope,
                include_files=include_files,
                max_nodes=260,
            )
            self._scope_cache[cache_key] = world

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

        zoom_ratio = (self._zoom - 0.45) / (3.4 - 0.45)
        zoom_ratio = max(0.0, min(1.0, zoom_ratio))
        filled = int(zoom_ratio * 10)
        zoom_bar = "[" + ("#" * filled) + ("-" * (10 - filled)) + "]"

        self._set_hud(
            f"scope={self.current_scope.relative_to(self.repo_root) if self.current_scope != self.repo_root else '.'}  "
            f"zoom={self._zoom:.2f}{zoom_bar}  nodes={len(self._world.nodes)}  "
            "controls: arrows pan | ctrl+up/down zoom | tab cycle | g snap | enter drill | b back | f fit"
        )
        self._render_minimap()

    def _render_minimap(self) -> None:
        minimap = self.query_one("#minimap", Static)
        if self._world is None or not self._world.nodes:
            minimap.update("[dim]minimap unavailable[/]")
            return

        w = 28
        h = 10
        grid = [[" " for _ in range(w)] for _ in range(h)]

        min_x = min(n.x for n in self._world.nodes)
        max_x = max(n.x for n in self._world.nodes)
        min_y = min(n.y for n in self._world.nodes)
        max_y = max(n.y for n in self._world.nodes)

        span_x = max(1.0, max_x - min_x)
        span_y = max(1.0, max_y - min_y)

        for node in self._world.nodes:
            gx = int(((node.x - min_x) / span_x) * (w - 1))
            gy = int(((node.y - min_y) / span_y) * (h - 1))
            char = "D" if node.is_dir else "."
            if node.id == self._selected_id:
                char = "X"
            grid[gy][gx] = char

        cam_x = int(((self._camera_x - min_x) / span_x) * (w - 1))
        cam_y = int(((self._camera_y - min_y) / span_y) * (h - 1))
        if 0 <= cam_x < w and 0 <= cam_y < h:
            grid[cam_y][cam_x] = "+"

        body = "\n".join("".join(row) for row in grid)
        minimap.update(f"[bold cyan]MINIMAP[/]\n{body}")

    def _selected_node(self) -> WorldNode | None:
        if self._world is None or self._selected_id is None:
            return None
        return next((n for n in self._world.nodes if n.id == self._selected_id), None)

    def _ordered_nodes(self) -> list[WorldNode]:
        if self._world is None:
            return []
        return sorted(
            self._world.nodes,
            key=lambda n: (
                not n.is_dir,
                (n.x - self._camera_x) ** 2 + (n.y - self._camera_y) ** 2,
                n.name.lower(),
            ),
        )

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
        self._scope_cache.clear()
        self._set_hud("Rescanning world")
        self.run_worker(self._load_scope_async(self.current_scope), exclusive=True)

    def action_select_next_node(self) -> None:
        nodes = self._ordered_nodes()
        if not nodes:
            return
        if self._selected_id is None:
            self._selected_id = nodes[0].id
        else:
            idx = next((i for i, n in enumerate(nodes) if n.id == self._selected_id), -1)
            self._selected_id = nodes[(idx + 1) % len(nodes)].id
        self._render_world()

    def action_select_prev_node(self) -> None:
        nodes = self._ordered_nodes()
        if not nodes:
            return
        if self._selected_id is None:
            self._selected_id = nodes[-1].id
        else:
            idx = next((i for i, n in enumerate(nodes) if n.id == self._selected_id), -1)
            self._selected_id = nodes[(idx - 1) % len(nodes)].id
        self._render_world()

    def action_snap_to_selected(self) -> None:
        node = self._selected_node()
        if node is None:
            return
        self._camera_x = node.x
        self._camera_y = node.y
        self._render_world()

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
            self._set_hud(f"Entering {node.name}...")
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
        self._set_hud(f"Returning to {previous.name}...")
        self.run_worker(self._load_scope_async(previous), exclusive=True)

    def on_world_viewport_node_focused(self, message: WorldViewport.NodeFocused) -> None:
        if message.node is None:
            return
        self._selected_id = message.node.id
        self._set_inspector_for_node(message.node)

    def on_world_viewport_node_activated(self, message: WorldViewport.NodeActivated) -> None:
        self._selected_id = message.node.id
        self.action_drill_or_open()
