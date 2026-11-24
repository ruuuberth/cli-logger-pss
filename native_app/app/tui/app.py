"""Interactive TUI shell for PSS Logger (issue #47).

Slice 2 adds the battle explorer: a paginated table fed by the existing
CLI service, with slow queries in a Textual worker. The app only renders —
no application logic of its own. The detail screen and the live dashboard
land in the next slices.
"""

from __future__ import annotations

from typing import Any

from textual import work
from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.reactive import reactive
from textual.widgets import (
    DataTable,
    Footer,
    Header,
    Label,
    TabbedContent,
    TabPane,
)

from app.cli.cli_services import ApiFlowCliService, CharacterCliService, RoomCliService
from app.services.api_flow_runtime import ApiFlowRuntime

PAGE_SIZE = 20


class PssTuiApp(App):
    """Dashboard + battle explorer over the existing SQLite data."""

    TITLE = "PSS Logger"
    SUB_TITLE = "Dashboard / Explorador de Batallas"
    # DataTable owns enter/left/right while focused, so paging uses n/p.
    BINDINGS = [
        ("q", "quit", "Salir"),
        ("r", "reload", "Recargar"),
        ("n", "next_page", "Pág. siguiente"),
        ("p", "prev_page", "Pág. anterior"),
    ]

    page: reactive[int] = reactive(0)
    total_rows: reactive[int] = reactive(0)

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
        self.search = ""

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
                yield DataTable(id="table-battles", cursor_type="row")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#table-battles", DataTable)
        table.add_columns(
            "Fecha", "Atacante", "Defensor", "Resultado", "Botín", "Trofeos"
        )
        table.focus()
        self.query_one("#lbl-help", Label).update(
            "q salir · n/p páginas · r recargar · enter detalle · (búsqueda y dashboard en vivo: siguientes PRs)"
        )
        self.action_reload()

    # -- data loading ------------------------------------------------------

    def action_reload(self) -> None:
        """Reload the current page from SQLite in a worker thread."""
        self._reload_page(self.page, self.search)

    @work(thread=True, exclusive=True, group="reload")
    def _reload_page(self, page: int, search: str) -> None:
        try:
            page_dto = self.service.query_events(
                search=search, page=page, page_size=PAGE_SIZE
            )
        except Exception as exc:  # DB missing/empty must not crash the TUI
            self.call_from_thread(self._show_error, str(exc))
            return
        self.call_from_thread(self._render_page, page_dto)

    def _render_page(self, page_dto: Any) -> None:
        """Render a fetched page (always called on the UI thread)."""
        if not self.is_mounted:
            return
        self.total_rows = page_dto.total
        table = self.query_one("#table-battles", DataTable)
        table.clear()
        for row in page_dto.rows:
            row_id = row.battle_replay_id or row.api_flow_event_id
            if row_id is None:
                continue
            table.add_row(
                row.captured_at_label,
                row.attacker_label,
                row.defender_label,
                row.outcome_label,
                row.loot_label,
                row.trophy_delta_label,
                key=str(row_id),
            )
        status = self.query_one("#lbl-status", Label)
        if page_dto.rows:
            status.update("")
            table.move_cursor(row=0)
        else:
            status.update("Sin batallas capturadas todavía · r recargar")

    def _show_error(self, message: str) -> None:
        if not self.is_mounted:
            return
        self.query_one("#lbl-status", Label).update(f"Error: {message}")
        self.notify(message, severity="error", title="Error")

    # -- paging --------------------------------------------------------------

    def _can_prev_page(self) -> bool:
        return self.page > 0

    def _can_next_page(self) -> bool:
        # total_rows is set by the async reload worker; allow a probe page
        # turn when the total is still unknown (first mount race).
        return self.total_rows == 0 or (self.page + 1) * PAGE_SIZE < self.total_rows

    def action_prev_page(self) -> None:
        if self._can_prev_page():
            self.page -= 1
            self.action_reload()

    def action_next_page(self) -> None:
        if self._can_next_page():
            self.page += 1
            self.action_reload()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id != "table-battles":
            return
        raw_key = event.row_key.value
        if not raw_key:
            return
        try:
            battle_replay_id = int(raw_key)
        except ValueError:
            return
        from app.tui.screens import BattleDetailScreen

        self.push_screen(
            BattleDetailScreen(
                battle_replay_id, self.service, self.characters, self.rooms
            )
        )


def run_tui(capture_runtime: ApiFlowRuntime | None = None) -> None:
    """Entry point used by `pss-native --tui`."""
    PssTuiApp(capture_runtime=capture_runtime).run()
