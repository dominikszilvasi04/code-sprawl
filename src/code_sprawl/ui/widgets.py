from __future__ import annotations

from math import sqrt

from textual import events
from textual.message import Message
from textual.widgets import Static

from ..models import WorldNode, WorldScope


class WorldViewport(Static):
    class NodeFocused(Message):
        def __init__(self, node: WorldNode | None) -> None:
            self.node = node
            super().__init__()

    class NodeActivated(Message):
        def __init__(self, node: WorldNode) -> None:
            self.node = node
            super().__init__()

    def __init__(self) -> None:
        super().__init__(id="world-view")
        self.scope: WorldScope | None = None
        self.camera_x = 0.0
        self.camera_y = 0.0
        self.zoom = 1.0
        self.selected_id: str | None = None
        self._phase = 0

    def on_mount(self) -> None:
        self.set_interval(0.28, self._animate)

    def _animate(self) -> None:
        self._phase = (self._phase + 1) % 6
        self.refresh(layout=False)

    def set_world(self, scope: WorldScope) -> None:
        self.scope = scope
        if self.selected_id is None and scope.nodes:
            self.selected_id = scope.nodes[0].id
        self.refresh(layout=False)

    def set_camera(self, x: float, y: float, zoom: float) -> None:
        self.camera_x = x
        self.camera_y = y
        self.zoom = zoom
        self.refresh(layout=False)

    def set_selected(self, node_id: str | None) -> None:
        self.selected_id = node_id
        self.refresh(layout=False)

    def selected_node(self) -> WorldNode | None:
        if self.scope is None or self.selected_id is None:
            return None
        return next((n for n in self.scope.nodes if n.id == self.selected_id), None)

    def _to_screen(self, node: WorldNode, width: int, height: int) -> tuple[int, int, int]:
        sx = int((node.x - self.camera_x) * self.zoom + width / 2)
        sy = int((node.y - self.camera_y) * self.zoom + height / 2)
        radius = max(1, int(node.radius * self.zoom))
        return sx, sy, radius

    def _pick_node(self, world_x: float, world_y: float) -> WorldNode | None:
        if self.scope is None:
            return None

        best: tuple[float, WorldNode] | None = None
        for node in self.scope.nodes:
            dx = world_x - node.x
            dy = world_y - node.y
            d = sqrt(dx * dx + dy * dy)
            threshold = max(2.0 / max(0.4, self.zoom), node.radius * 1.25)
            if d <= threshold:
                if best is None or d < best[0]:
                    best = (d, node)

        return best[1] if best else None

    def on_click(self, event: events.Click) -> None:
        width = max(1, self.size.width)
        height = max(1, self.size.height)

        world_x = ((event.x - (width / 2)) / max(0.4, self.zoom)) + self.camera_x
        world_y = ((event.y - (height / 2)) / max(0.4, self.zoom)) + self.camera_y

        node = self._pick_node(world_x, world_y)
        if node is None:
            return

        already_selected = node.id == self.selected_id
        self.selected_id = node.id
        self.post_message(self.NodeFocused(node))

        if already_selected and event.chain >= 2:
            self.post_message(self.NodeActivated(node))

    def render(self) -> str:
        width = max(16, self.size.width)
        height = max(8, self.size.height)

        buffer = [[" " for _ in range(width)] for _ in range(height)]

        if self.scope is None:
            return "Loading world..."

        seed = (self._phase * 7) % 17
        for y in range(0, height, 3):
            x = ((y * 11) + seed) % max(1, width)
            buffer[y][x] = "."

        nodes = sorted(self.scope.nodes, key=lambda n: (n.is_dir, n.radius), reverse=True)

        for node in nodes:
            sx, sy, radius = self._to_screen(node, width, height)

            if sx < -radius - 20 or sx > width + radius + 20 or sy < -radius - 5 or sy > height + radius + 5:
                continue

            if node.is_dir:
                self._draw_blob(buffer, node, sx, sy, radius)
                self._draw_label(buffer, sx, sy + radius + 1, node.name)
            else:
                self._draw_file_node(buffer, node, sx, sy)

            if self.selected_id == node.id:
                self._draw_selection_ring(buffer, sx, sy, radius + 1)

        cx = width // 2
        cy = height // 2
        if 0 <= cx < width and 0 <= cy < height:
            buffer[cy][cx] = "+"

        return "\n".join("".join(row) for row in buffer)

    def _draw_blob(self, buffer: list[list[str]], node: WorldNode, sx: int, sy: int, radius: int) -> None:
        height = len(buffer)
        width = len(buffer[0]) if buffer else 0

        if node.debt_level == "critical":
            fill_char = "#"
            edge_char = "@"
            core_char = "X"
        elif node.debt_level == "high":
            fill_char = "&"
            edge_char = "%"
            core_char = "H"
        else:
            fill_char = "o"
            edge_char = "O"
            core_char = "D"

        if node.commit_count >= 20:
            fill_char = "*"

        for dy in range(-radius - 1, radius + 2):
            py = sy + dy
            if py < 0 or py >= height:
                continue
            for dx in range(-radius - 2, radius + 3):
                px = sx + dx
                if px < 0 or px >= width:
                    continue

                dist = sqrt((dx * 0.9) ** 2 + (dy * 1.15) ** 2)
                edge_noise = ((hash((node.id, dx, dy, self._phase)) % 100) / 100.0 - 0.5) * 0.35
                limit = radius + edge_noise
                if dist <= limit:
                    if abs(dist - radius) <= 0.8:
                        buffer[py][px] = edge_char
                    else:
                        buffer[py][px] = fill_char

        if 0 <= sx < width and 0 <= sy < height:
            pulse = core_char if self._phase % 2 == 0 else "+"
            buffer[sy][sx] = pulse

    def _draw_file_node(self, buffer: list[list[str]], node: WorldNode, sx: int, sy: int) -> None:
        height = len(buffer)
        width = len(buffer[0]) if buffer else 0
        if sy < 1 or sy >= height - 1 or sx < 1 or sx >= width - 1:
            return

        char = "•"
        if node.debt_level in {"high", "critical"}:
            char = "x" if self._phase % 2 == 0 else "X"
        elif node.commit_count >= 12:
            char = "*" if self._phase % 2 == 0 else "+"

        buffer[sy][sx] = char
        buffer[sy - 1][sx] = "^"
        buffer[sy + 1][sx] = "v"

    def _draw_label(self, buffer: list[list[str]], sx: int, sy: int, text: str) -> None:
        if sy < 0 or sy >= len(buffer):
            return
        width = len(buffer[sy])

        label = text if len(text) <= 14 else f"{text[:11]}..."
        start = sx - len(label) // 2
        for i, ch in enumerate(label):
            x = start + i
            if 0 <= x < width:
                buffer[sy][x] = ch

    def _draw_selection_ring(self, buffer: list[list[str]], sx: int, sy: int, radius: int) -> None:
        height = len(buffer)
        width = len(buffer[0]) if buffer else 0

        ring_char = "~" if self._phase % 2 == 0 else "="
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                dist = sqrt(dx * dx + dy * dy)
                if abs(dist - radius) <= 0.65:
                    py = sy + dy
                    px = sx + dx
                    if 0 <= px < width and 0 <= py < height and buffer[py][px] == " ":
                        buffer[py][px] = ring_char
