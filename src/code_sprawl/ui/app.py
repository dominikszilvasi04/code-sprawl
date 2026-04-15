from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path

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
        ("s", "cycle_sort", "Sort"),
        ("d", "cycle_debt_filter", "Debt"),
        ("e", "toggle_empty", "Empty Dirs"),
        ("]", "more_density", "More Buildings"),
        ("[", "less_density", "Fewer Buildings"),
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

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label("Code-Sprawl // scan your repo, hunt debt, vibe in neon", id="banner")
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

    def action_reload(self) -> None:
        self._set_sidebar("Rescanning...", "Rebuilding districts and recalculating debt.")
        city_pane = self.query_one("#city-pane", Vertical)
        city_pane.remove_children()
        city_pane.mount(Static("[cyan]Rescanning repository...[/]"))
        self.run_worker(self._load_city_async(), exclusive=True)

    def action_cycle_sort(self) -> None:
        self._sort_index = (self._sort_index + 1) % len(self._sort_modes)
        self._district_page = 0
        self._rerender_if_loaded()

    def action_cycle_debt_filter(self) -> None:
        self._debt_filter_index = (self._debt_filter_index + 1) % len(self._debt_filters)
        self._district_page = 0
        self._rerender_if_loaded()

    def action_toggle_empty(self) -> None:
        self._show_empty_districts = not self._show_empty_districts
        self._district_page = 0
        self._rerender_if_loaded()

    def action_more_density(self) -> None:
        self._max_buildings_per_district = min(160, self._max_buildings_per_district + 16)
        self._rerender_if_loaded()

    def action_less_density(self) -> None:
        self._max_buildings_per_district = max(16, self._max_buildings_per_district - 16)
        self._rerender_if_loaded()

    def action_next_page(self) -> None:
        if self._snapshot is None:
            return
        visible = self._filtered_sorted_districts(self._snapshot)
        max_page = max(0, (len(visible) - 1) // self._districts_per_page)
        self._district_page = min(max_page, self._district_page + 1)
        self._render_snapshot(self._snapshot)

    def action_prev_page(self) -> None:
        if self._snapshot is None:
            return
        self._district_page = max(0, self._district_page - 1)
        self._render_snapshot(self._snapshot)

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

    def _filtered_sorted_districts(self, snapshot: CitySnapshot) -> list[District]:
        threshold = self._debt_threshold_rank()
        filtered_districts = []

        sort_mode = self._sort_modes[self._sort_index]

        for district in snapshot.districts:
            buildings = [
                b for b in district.buildings if self._debt_level_rank(b.debt_level) >= threshold
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

        districts_all = self._filtered_sorted_districts(snapshot)
        max_page = max(0, (len(districts_all) - 1) // self._districts_per_page)
        self._district_page = min(self._district_page, max_page)

        start = self._district_page * self._districts_per_page
        end = start + self._districts_per_page
        districts = districts_all[start:end]

        for district in districts:
            city_pane.mount(DistrictWidget(district, max_buildings=self._max_buildings_per_district))

        if not districts_all:
            city_pane.mount(Static("[yellow]No folders matched current filters.[/]"))

        weather = "CLOUDY" if snapshot.todo_count >= 25 else "CLEAR"
        current_page = self._district_page + 1
        total_pages = max(1, (len(districts_all) + self._districts_per_page - 1) // self._districts_per_page)
        hidden_by_page = max(0, len(districts_all) - len(districts))
        sort_mode = self._sort_modes[self._sort_index]
        debt_filter = self._debt_filters[self._debt_filter_index]
        self._set_sidebar(
            title="Welcome to the Sprawl",
            body=(
                f"Root: {snapshot.root}\n"
                f"Districts: {len(snapshot.districts)}\n"
                f"Visible districts: {len(districts_all)}\n"
                f"View: page {current_page}/{total_pages} (n/p to navigate)\n"
                f"Sort: {sort_mode} | Debt: {debt_filter}\n"
                f"Density cap: {self._max_buildings_per_district} per district\n"
                f"Show empty: {'ON' if self._show_empty_districts else 'OFF'}\n"
                f"Repo TODOs: {snapshot.todo_count} {weather}\n"
                f"Skipped dirs: {snapshot.scan_stats.dirs_skipped_builtin} builtin, "
                f"{snapshot.scan_stats.dirs_skipped_gitignore} gitignored\n"
                f"Skipped files: {snapshot.scan_stats.files_skipped_gitignore} gitignored, "
                f"{snapshot.scan_stats.files_skipped_non_text} non-text\n"
                f"Hidden by paging: {hidden_by_page}\n"
                f"Scanned: {snapshot.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                "Controls: n/p pages, s sort, d debt, e empty, [ ] density\n"
                "Click any building to inspect details."
            ),
        )

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
