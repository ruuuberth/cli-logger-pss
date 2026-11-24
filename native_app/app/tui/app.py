"""Interactive TUI shell for PSS Logger (issue #47).

First slice: `pss-native --tui` boots this Textual app over the existing
env/DB/logging bootstrap. The app only renders — all data comes from the
CLI services. The battle explorer (data) and the detail screen land in the
follow-up PRs of this feature.
"""

from __future__ import annotations

from typing import Any

from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widgets import Footer, Header, Label, TabbedContent, TabPane

from app.cli.cli_services import ApiFlowCliService, CharacterCliService, RoomCliService
from app.services.api_flow_runtime import ApiFlowRuntime


class PssTuiApp(App):
    """Dashboard + battle explorer over the existing SQLite data."""

    TITLE = "PSS Logger"
    SUB_TITLE = "Dashboard / Explorador de Batallas"
    BINDINGS = [("q", "quit", "Salir")]

    def __init__(
        self,
        capture_runtime: ApiFlowRuntime | None = None,
        cli_service: Any = None,
        character_service: Any = None,
        room_service: Any = None,
    ) -> None:
        super().__init__()
        self.runtime = capture_runtime
        self.service = cli_service or ApiFlowCliService()
        self.characters = character_service or CharacterCliService()
        self.rooms = room_service or RoomCliService()

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent():
            with TabPane("Dashboard", id="tab-dashboard"):
                yield Vertical(
                    Label("", id="lbl-capture"),
                    Label("", id="lbl-events"),
                    Label("", id="lbl-status"),
                    Label("", id="lbl-help"),
                )
            with TabPane("Batallas", id="tab-battles"):
                yield Label(
                    "Explorador de batallas: pendiente (siguiente PR).",
                    id="lbl-todo",
                )
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#lbl-help", Label).update(
            "q salir · el explorador de batallas llega en el siguiente PR"
        )


def run_tui(capture_runtime: ApiFlowRuntime | None = None) -> None:
    """Entry point used by `pss-native --tui`."""
    PssTuiApp(capture_runtime=capture_runtime).run()
