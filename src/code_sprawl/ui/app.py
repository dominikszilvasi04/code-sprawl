from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path

from textual import events
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Label, Static

from ..models import Building, CitySnapshot, District
from ..scanner import scan_repository
from .widgets import BuildingWidget, DistrictWidget


class CodeSprawlApp(App):
    CSS_PATH = "styles.tcss"
    TITLE = "Code-Sprawl"
    SUB_TITLE = "Neon repo skyline"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "reload", "Rescan"),
        ("n", "next_page", "Next Districts"),
        ("p", "prev_page", "Prev Districts"),
        ("j", "next_district", "Next District"),
        ("k", "prev_district", "Prev District"),
        ("enter", "focus_selected", "Focus District"),
        ("b", "clear_focus", "Back to All"),
        ("s", "cycle_sort", "Sort"),
        ("d", "cycle_debt_filter", "Debt"),
        ("x", "cycle_extension_filter", "Ext Filter"),
        ("e", "toggle_empty", "Empty Dirs"),
        ("]", "more_density", "More Buildings"),
        ("[", "less_density", "Fewer Buildings"),
        ("=", "more_districts", "More Districts"),
        ("-", "less_districts", "Fewer Districts"),
        ("period", "wider_street", "Wider Streets"),
        ("comma", "narrower_street", "Narrower Streets"),
    ]

    def __init__(self, repo_path: Path) -> None:
        super().__init__()
        self.repo_path = repo_path
        self._snapshot: CitySnapshot | None = None
        self._district_page = 0
        self._districts_per_page = 6
        self._show_empty_districts = True
        self._max_buildings_per_district = 64
        self._sort_modes = ("size", "hot", "debt", "name")
        self._sort_index = 0
        self._debt_filters = ("all", "medium+", "high+", "critical")
        self._debt_filter_index = 0
        self._extension_filters = ("all", "python", "web", "docs", "config")
        self._extension_filter_index = 0
        self._selected_district_index = 0
        self._focused_district_name: str | None = None
        self._columns_per_row = 22
        self._manual_street_width = False

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label("Code-Sprawl // scan your repo, hunt debt, vibe in neon", id="banner")
        yield Static(id="district-strip")
        with Horizontal(id="main-layout"):
            yield Vertical(id="city-pane")
            yield Static(id="sidebar")
        with Vertical(id="timeline-panel"):
            yield Label("Time Travel (preview mode)", id="timeline-title")
            yield Static("[cyan]████████████████████[/]  NOW", id="timeline")
        yield Footer()

    def on_mount(self) -> None:
        self._set_sidebar("Scanning...", "Warming up the neon skyline. Please wait.")
        city_pane = self.query_one("#city-pane", Vertical)
        city_pane.remove_children()
        city_pane.mount(Static("[cyan]Scanning repository...[/]"))
        self.run_worker(self._load_city_async(), exclusive=True)

    def on_resize(self, event: events.Resize) -> None:
        self._recompute_columns_per_row()
        self._rerender_if_loaded()

    def action_reload(self) -> None:
        self._set_sidebar("Rescanning...", "Rebuilding districts and recalculating debt.")
        city_pane = self.query_one("#city-pane", Vertical)
        city_pane.remove_children()
        city_pane.mount(Static("[cyan]Rescanning repository...[/]"))
        self.run_worker(self._load_city_async(), exclusive=True)

    def action_cycle_sort(self) -> None:
        self._sort_index = (self._sort_index + 1) % len(self._sort_modes)
        self._district_page = 0
        self._selected_district_index = 0
        self._rerender_if_loaded()

    def action_cycle_debt_filter(self) -> None:
        self._debt_filter_index = (self._debt_filter_index + 1) % len(self._debt_filters)
        self._district_page = 0
        self._selected_district_index = 0
        self._rerender_if_loaded()

    def action_cycle_extension_filter(self) -> None:
        self._extension_filter_index = (self._extension_filter_index + 1) % len(self._extension_filters)
        self._district_page = 0
        self._selected_district_index = 0
        self._rerender_if_loaded()

    def action_toggle_empty(self) -> None:
        self._show_empty_districts = not self._show_empty_districts
        self._district_page = 0
        self._selected_district_index = 0
        self._rerender_if_loaded()

    def action_more_density(self) -> None:
        self._max_buildings_per_district = min(160, self._max_buildings_per_district + 16)
        self._rerender_if_loaded()

    def action_less_density(self) -> None:
        self._max_buildings_per_district = max(16, self._max_buildings_per_district - 16)
        self._rerender_if_loaded()

    def action_more_districts(self) -> None:
        self._districts_per_page = min(12, self._districts_per_page + 1)
        self._district_page = 0
        self._selected_district_index = 0
        self._rerender_if_loaded()

    def action_less_districts(self) -> None:
        self._districts_per_page = max(2, self._districts_per_page - 1)
        self._district_page = 0
        self._selected_district_index = 0
        self._rerender_if_loaded()

    def action_wider_street(self) -> None:
        self._manual_street_width = True
        self._columns_per_row = max(6, self._columns_per_row - 2)
        self._rerender_if_loaded()

    def action_narrower_street(self) -> None:
        self._manual_street_width = True
        self._columns_per_row = min(48, self._columns_per_row + 2)
        self._rerender_if_loaded()

    def action_next_page(self) -> None:
        if self._snapshot is None:
            return
        visible = self._districts_for_view(self._snapshot)
        max_page = max(0, (len(visible) - 1) // self._districts_per_page)
        self._district_page = min(max_page, self._district_page + 1)
        self._selected_district_index = min(
            len(visible) - 1,
            self._district_page * self._districts_per_page,
        )
        self._render_snapshot(self._snapshot)

    def action_prev_page(self) -> None:
        if self._snapshot is None:
            return
        self._district_page = max(0, self._district_page - 1)
        visible = self._districts_for_view(self._snapshot)
        if visible:
            self._selected_district_index = min(
                len(visible) - 1,
                self._district_page * self._districts_per_page,
            )
        self._render_snapshot(self._snapshot)

    def action_next_district(self) -> None:
        if self._snapshot is None:
            return
        districts = self._districts_for_view(self._snapshot)
        if not districts:
            return
        self._selected_district_index = min(len(districts) - 1, self._selected_district_index + 1)
        self._district_page = self._selected_district_index // self._districts_per_page
        self._render_snapshot(self._snapshot)

    def action_prev_district(self) -> None:
        if self._snapshot is None:
            return
        districts = self._districts_for_view(self._snapshot)
        if not districts:
            return
        self._selected_district_index = max(0, self._selected_district_index - 1)
        self._district_page = self._selected_district_index // self._districts_per_page
        self._render_snapshot(self._snapshot)

    def action_focus_selected(self) -> None:
        if self._snapshot is None:
            return
        districts = self._filtered_sorted_districts(self._snapshot)
        if not districts:
            return
        self._selected_district_index = min(self._selected_district_index, len(districts) - 1)
        self._focused_district_name = districts[self._selected_district_index].name
        self._district_page = 0
        self._selected_district_index = 0
        self._render_snapshot(self._snapshot)

    def action_clear_focus(self) -> None:
        if self._focused_district_name is None:
            return
        self._focused_district_name = None
        self._district_page = 0
        self._selected_district_index = 0
        self._rerender_if_loaded()

    async def _load_city_async(self) -> None:
        snapshot = await asyncio.to_thread(
            scan_repository,
            self.repo_path,
            include_empty_districts=True,
        )
        self._snapshot = snapshot
        self._district_page = 0
        self._render_snapshot(snapshot)

    def _rerender_if_loaded(self) -> None:
        if self._snapshot is not None:
            self._render_snapshot(self._snapshot)

    def _recompute_columns_per_row(self) -> None:
        try:
            city_width = self.query_one("#city-pane", Vertical).size.width
        except Exception:
            return

        if city_width <= 0:
            return

        auto_columns = max(8, min(48, city_width // 4))
        if not self._manual_street_width:
            self._columns_per_row = auto_columns
        else:
            self._columns_per_row = max(6, min(48, self._columns_per_row))

    def _districts_for_view(self, snapshot: CitySnapshot) -> list[District]:
        districts = self._filtered_sorted_districts(snapshot)
        if self._focused_district_name:
            focused = [d for d in districts if d.name == self._focused_district_name]
            if focused:
                return focused
            self._focused_district_name = None
        return districts

    def _debt_level_rank(self, debt_level: str) -> int:
        return {"low": 0, "medium": 1, "high": 2, "critical": 3}.get(debt_level, 0)

    def _debt_threshold_rank(self) -> int:
        mode = self._debt_filters[self._debt_filter_index]
        return {
            "all": 0,
            "medium+": 1,
            "high+": 2,
            "critical": 3,
        }[mode]

    def _matches_extension_filter(self, extension: str) -> bool:
        mode = self._extension_filters[self._extension_filter_index]
        ext = extension.lower()

        if mode == "all":
            return True
        if mode == "python":
            return ext == ".py"
        if mode == "web":
            return ext in {".js", ".jsx", ".ts", ".tsx", ".css", ".scss", ".html"}
        if mode == "docs":
            return ext in {".md", ".txt", ".rst"}
        if mode == "config":
            return ext in {".json", ".yaml", ".yml", ".toml", ".ini", ".cfg"}
        return True

    def _filtered_sorted_districts(self, snapshot: CitySnapshot) -> list[District]:
        threshold = self._debt_threshold_rank()
        filtered_districts = []

        sort_mode = self._sort_modes[self._sort_index]

        for district in snapshot.districts:
            buildings = [
                b
                for b in district.buildings
                if self._debt_level_rank(b.debt_level) >= threshold
                and self._matches_extension_filter(b.extension)
            ]

            if sort_mode == "size":
                buildings.sort(key=lambda b: (b.loc, b.commit_count), reverse=True)
            elif sort_mode == "hot":
                buildings.sort(key=lambda b: (b.commit_count, b.loc), reverse=True)
            elif sort_mode == "debt":
                buildings.sort(key=lambda b: (b.complexity, b.loc), reverse=True)
            else:
                buildings.sort(key=lambda b: b.name.lower())

            if buildings or self._show_empty_districts:
                filtered_districts.append(replace(district, buildings=buildings))

        filtered_districts.sort(key=lambda d: (len(d.buildings), d.name), reverse=True)
        return filtered_districts

    def _render_snapshot(self, snapshot: CitySnapshot) -> None:
        city_pane = self.query_one("#city-pane", Vertical)
        city_pane.remove_children()

        districts_all = self._districts_for_view(snapshot)
        if districts_all:
            self._selected_district_index = min(self._selected_district_index, len(districts_all) - 1)
        else:
            self._selected_district_index = 0

        max_page = max(0, (len(districts_all) - 1) // self._districts_per_page)
        self._district_page = min(self._district_page, max_page)

        start = self._district_page * self._districts_per_page
        end = start + self._districts_per_page
        districts = districts_all[start:end]

        self._render_district_strip(districts_all)

        for offset, district in enumerate(districts):
            absolute_index = start + offset
            city_pane.mount(
                DistrictWidget(
                    district,
                    max_buildings=self._max_buildings_per_district,
                    selected=absolute_index == self._selected_district_index,
                    columns_per_row=self._columns_per_row,
                )
            )

        if not districts_all:
            city_pane.mount(Static("[yellow]No folders matched current filters.[/]"))

        weather = "CLOUDY" if snapshot.todo_count >= 25 else "CLEAR"
        current_page = self._district_page + 1
        total_pages = max(1, (len(districts_all) + self._districts_per_page - 1) // self._districts_per_page)
        hidden_by_page = max(0, len(districts_all) - len(districts))
        sort_mode = self._sort_modes[self._sort_index]
        debt_filter = self._debt_filters[self._debt_filter_index]
        extension_filter = self._extension_filters[self._extension_filter_index]
        focus_state = self._focused_district_name or "(all)"
        self._set_sidebar(
            title="Welcome to the Sprawl",
            body=(
                f"Root: {snapshot.root}\n"
                f"Districts: {len(snapshot.districts)}\n"
                f"Visible districts: {len(districts_all)}\n"
                f"View: page {current_page}/{total_pages} (n/p to navigate)\n"
            f"Focused district: {focus_state}\n"
                f"Sort: {sort_mode} | Debt: {debt_filter} | Ext: {extension_filter}\n"
                f"Districts/page: {self._districts_per_page}\n"
                f"Density cap: {self._max_buildings_per_district} per district\n"
                f"Street width: {self._columns_per_row} columns\n"
                f"Show empty: {'ON' if self._show_empty_districts else 'OFF'}\n"
                f"Repo TODOs: {snapshot.todo_count} {weather}\n"
                f"Skipped dirs: {snapshot.scan_stats.dirs_skipped_builtin} builtin, "
                f"{snapshot.scan_stats.dirs_skipped_gitignore} gitignored\n"
                f"Skipped files: {snapshot.scan_stats.files_skipped_gitignore} gitignored, "
                f"{snapshot.scan_stats.files_skipped_non_text} non-text\n"
                f"Hidden by paging: {hidden_by_page}\n"
                f"Scanned: {snapshot.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                "Controls: n/p page, j/k district, Enter focus, b back\n"
                "More: s sort, d debt, x ext, e empty, [ ] density, -/= districts, ,/. streets\n"
                "Click any building to inspect details."
            ),
        )

    def _render_district_strip(self, districts_all: list[District]) -> None:
        strip = self.query_one("#district-strip", Static)
        if not districts_all:
            strip.update("[dim]DISTRICTS: none[/]")
            return

        items: list[str] = []
        start = max(0, self._selected_district_index - 6)
        end = min(len(districts_all), start + 13)

        for idx in range(start, end):
            name = districts_all[idx].name
            short = name if len(name) <= 16 else f"...{name[-13:]}"
            if idx == self._selected_district_index:
                items.append(f"[bold black on cyan] {short} [/]")
            else:
                items.append(f"[cyan]{short}[/]")

        mode = "FOCUS" if self._focused_district_name else "ALL"
        strip.update(f"[bold]DISTRICTS[{mode}][/]: " + "  ".join(items))

    def _set_sidebar(self, title: str, body: str) -> None:
        sidebar = self.query_one("#sidebar", Static)
        sidebar.update(f"[bold magenta]{title}[/]\n\n{body}")

    def on_building_widget_selected(self, message: BuildingWidget.Selected) -> None:
        b: Building = message.building
        freshness = "shiny" if b.age_days <= 7 else "aging" if b.age_days <= 60 else "rusty"
        self._set_sidebar(
            title=b.name,
            body=(
                f"Path: {b.path}\n"
                f"Extension: {b.extension}\n"
                f"LoC: {b.loc}\n"
                f"Height: {b.height} floors\n"
                f"Age: {b.age_days} days ({freshness})\n"
                f"Commits (sampled): {b.commit_count}\n"
                f"Complexity: {b.complexity:.1f} ({b.debt_level})\n"
                f"TODOs: {b.todo_count}\n"
            ),
        )
