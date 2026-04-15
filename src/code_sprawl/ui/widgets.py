from __future__ import annotations

from textual import events
from textual.containers import Horizontal
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
        self._phase = 0

        ext_class = building.extension[1:] if building.extension.startswith(".") else "none"
        self.add_class(f"ext-{ext_class}".replace("+", "plus"))

        if building.debt_level in {"high", "critical"}:
            self.add_class("high-debt")
        if building.commit_count >= 10:
            self.add_class("high-heat")

    def on_enter(self, event: events.Enter) -> None:
        self._hovered = True
        self.update(self.render_city_block())

    def on_leave(self, event: events.Leave) -> None:
        self._hovered = False
        self.update(self.render_city_block())

    def on_click(self, event: events.Click) -> None:
        self.post_message(self.Selected(self.building))

    def on_mount(self) -> None:
        if self.building.commit_count >= 10 or self.building.debt_level == "critical":
            self.set_interval(0.8, self._tick)
        self.update(self.render_city_block())

    def _tick(self) -> None:
        self._phase = (self._phase + 1) % 2
        self.update(self.render_city_block())

    def render_city_block(self) -> str:
        if self.building.debt_level == "critical":
            roof = "┏┳┓"
            body_unit = "┃X┃" if self._phase == 0 else "┃#┃"
        elif self.building.debt_level == "high":
            roof = "┏┯┓"
            body_unit = "┃▓┃" if self._phase == 0 else "┃▒┃"
        else:
            roof = "┌┬┐"
            if self.building.age_days <= 14:
                body_unit = "┃█┃" if self._phase == 0 else "┃▓┃"
            elif self.building.age_days <= 90:
                body_unit = "┃▒┃"
            else:
                body_unit = "┃░┃"

        if self.building.name.startswith(("main", "app", "index")):
            roof = "╭┬╮"

        body = "\n".join(body_unit for _ in range(self.building.height))
        base = "└┴┘"

        if self._hovered:
            return f"[bold cyan]{roof}[/]\n{body}\n{base}"
        return f"{roof}\n{body}\n{base}"


class DistrictWidget(Widget):
    def __init__(self, district: District, *, max_buildings: int = 64) -> None:
        super().__init__(classes="district")
        self.district = district
        self.max_buildings = max_buildings

    def compose(self):
        yield Label(
            f"{self.district.name}  [{len(self.district.buildings)} files]",
            classes="district-title",
        )
        visible = self.district.buildings[: self.max_buildings]
        if not visible:
            yield Static("(empty / filtered)", classes="district-empty")
            yield Static("─" * 80, classes="district-road")
            return

        per_row = 22
        for idx in range(0, len(visible), per_row):
            with Horizontal(classes="district-row"):
                for building in visible[idx : idx + per_row]:
                    yield BuildingWidget(building)
        yield Static("─" * 80, classes="district-road")
