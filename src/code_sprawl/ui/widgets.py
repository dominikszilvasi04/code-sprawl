from __future__ import annotations

from textual import events
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Label, Static

from ..models import Building, District


class BuildingWidget(Static):
    class Selected(Message):
        def __init__(self, building: Building) -> None:
            self.building = building
            super().__init__()

    def __init__(self, building: Building) -> None:
        super().__init__(classes="building")
        self.building = building
        self._hovered = False

        ext_class = building.extension[1:] if building.extension.startswith(".") else "none"
        self.add_class(f"ext-{ext_class}".replace("+", "plus"))

        if building.debt_level in {"high", "critical"}:
            self.add_class("high-debt")

    def on_enter(self, event: events.Enter) -> None:
        self._hovered = True
        self.update(self.render_city_block())

    def on_leave(self, event: events.Leave) -> None:
        self._hovered = False
        self.update(self.render_city_block())

    def on_click(self, event: events.Click) -> None:
        self.post_message(self.Selected(self.building))

    def on_mount(self) -> None:
        self.update(self.render_city_block())

    def render_city_block(self) -> str:
        if self.building.debt_level == "critical":
            window = "X"
        elif self.building.debt_level == "high":
            window = "▣"
        else:
            window = "▤"

        crown = "^^" if self.building.name.startswith(("main", "app", "index")) else "┏┓"
        body = "\n".join(f"┃{window}┃" for _ in range(self.building.height))
        base = "┗┛"

        if self._hovered:
            label = f"[bold cyan]{self.building.name[:10]}[/]"
        else:
            label = f"[dim]{self.building.extension}[/]"

        return f"{crown}\n{body}\n{base}\n{label}"


class DistrictWidget(Widget):
    def __init__(self, district: District) -> None:
        super().__init__(classes="district")
        self.district = district

    def compose(self):
        yield Label(f"◼ {self.district.name}", classes="district-title")
        with Horizontal(classes="district-row"):
            for building in self.district.buildings[:24]:
                yield BuildingWidget(building)
