from __future__ import annotations

import asyncio
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Footer, Header, Label, Static

from ..models import Building, CitySnapshot
from ..scanner import scan_repository
from .widgets import BuildingWidget, DistrictWidget


class CodeSprawlApp(App):
    CSS_PATH = "styles.tcss"
    TITLE = "Code-Sprawl"
    SUB_TITLE = "Neon repo skyline"
    BINDINGS = [("q", "quit", "Quit"), ("r", "reload", "Rescan")]

    def __init__(self, repo_path: Path) -> None:
        super().__init__()
        self.repo_path = repo_path

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label("Code-Sprawl // scan your repo, hunt debt, vibe in neon", id="banner")
        with Horizontal(id="main-layout"):
            yield VerticalScroll(id="city-pane")
            yield Static(id="sidebar")
        with Vertical(id="timeline-panel"):
            yield Label("Time Travel (preview mode)", id="timeline-title")
            yield Static("[cyan]████████████████████[/]  NOW", id="timeline")
        yield Footer()

    def on_mount(self) -> None:
        self._set_sidebar("Scanning...", "Warming up the neon skyline. Please wait.")
        city_pane = self.query_one("#city-pane", VerticalScroll)
        city_pane.remove_children()
        city_pane.mount(Static("[cyan]Scanning repository...[/]"))
        self.run_worker(self._load_city_async(), exclusive=True)

    def action_reload(self) -> None:
        self._set_sidebar("Rescanning...", "Rebuilding districts and recalculating debt.")
        city_pane = self.query_one("#city-pane", VerticalScroll)
        city_pane.remove_children()
        city_pane.mount(Static("[cyan]Rescanning repository...[/]"))
        self.run_worker(self._load_city_async(), exclusive=True)

    async def _load_city_async(self) -> None:
        snapshot = await asyncio.to_thread(scan_repository, self.repo_path)
        self._render_snapshot(snapshot)

    def _render_snapshot(self, snapshot: CitySnapshot) -> None:
        city_pane = self.query_one("#city-pane", VerticalScroll)
        city_pane.remove_children()

        for district in snapshot.districts:
            city_pane.mount(DistrictWidget(district))

        if not snapshot.districts:
            city_pane.mount(Static("[yellow]No scannable text files found in this path.[/]"))

        weather = "CLOUDY" if snapshot.todo_count >= 25 else "CLEAR"
        self._set_sidebar(
            title="Welcome to the Sprawl",
            body=(
                f"Root: {snapshot.root}\n"
                f"Districts: {len(snapshot.districts)}\n"
                f"Repo TODOs: {snapshot.todo_count} {weather}\n"
                f"Scanned: {snapshot.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
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
