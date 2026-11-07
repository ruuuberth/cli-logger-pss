"""Battle detail screen: ships / rooms / characters tabs (issue #47)."""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Label, TabbedContent, TabPane


class BattleDetailScreen(Screen):
    """Detail view for one battle, reusing the existing CLI services."""

    BINDINGS = [
        ("escape", "dismiss_screen", "Volver"),
        ("q", "dismiss_screen", "Volver"),
    ]

    def __init__(
        self,
        battle_replay_id: int,
        cli_service: Any,
        character_service: Any,
        room_service: Any,
    ) -> None:
        super().__init__()
        self.battle_replay_id = battle_replay_id
        self.service = cli_service
        self.characters = character_service
        self.rooms = room_service

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label("Cargando batalla…", id="lbl-summary")
        with TabbedContent():
            with TabPane("Naves", id="tab-ships"):
                yield DataTable(id="table-ships", cursor_type="row")
            with TabPane("Salas", id="tab-rooms"):
                yield DataTable(id="table-rooms", cursor_type="row")
            with TabPane("Tripulación", id="tab-crew"):
                yield DataTable(id="table-crew", cursor_type="row")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#table-ships", DataTable).add_columns("ID", "Lado", "Diseño")
        self.query_one("#table-rooms", DataTable).add_columns(
            "ID", "Lado", "Sala", "Posición"
        )
        self.query_one("#table-crew", DataTable).add_columns(
            "ID", "Nombre", "Lado", "Nivel"
        )
        self.run_worker(self._load_detail, thread=True, exclusive=True, group="detail")

    # -- loading (worker thread) -------------------------------------------

    def _load_detail(self) -> None:
        try:
            detail = self.service.get_battle_detail(self.battle_replay_id)
            ships = detail.get("ships", []) if detail else []
            rooms = self.rooms.list_rooms(self.battle_replay_id) if detail else []
            crew = (
                self.characters.list_characters(self.battle_replay_id) if detail else []
            )
        except Exception as exc:
            self.app.call_from_thread(self._render_load_error, str(exc))
            return
        self.app.call_from_thread(self._render_detail, detail, ships, rooms, crew)

    # -- rendering (UI thread) ---------------------------------------------

    def _render_detail(
        self,
        detail: dict | None,
        ships: list[dict],
        rooms: list[dict],
        crew: list[dict],
    ) -> None:
        if not self.is_mounted:
            return
        if not detail:
            self._render_summary(
                f"Batalla {self.battle_replay_id}: sin datos (¿aún no normalizada?)"
            )
            return
        replay = detail.get("replay") or {}
        self._render_summary(
            f"Batalla {replay.get('battle_id', self.battle_replay_id)}"
            f"  ·  capturada: {replay.get('captured_at') or '-'}"
            f"  ·  resultado: {replay.get('outcome_type') or '-'}"
        )

        ship_table = self.query_one("#table-ships", DataTable)
        ship_table.clear()
        for s in ships:
            ship_table.add_row(
                str(s.get("id", "-")),
                str(s.get("side", "-")),
                str(s.get("ship_design_name") or s.get("ship_design_id", "-")),
            )

        room_table = self.query_one("#table-rooms", DataTable)
        room_table.clear()
        for r in rooms:
            room_table.add_row(
                str(r.get("id", "-")),
                str(r.get("side", "-")),
                str(r.get("design_name") or "-"),
                f"({r.get('row', '-')},{r.get('column', '-')})",
            )

        crew_table = self.query_one("#table-crew", DataTable)
        crew_table.clear()
        for c in crew:
            crew_table.add_row(
                str(c.get("id", "-")),
                str(c.get("name") or "-"),
                str(c.get("side", "-")),
                str(c.get("level", "-")),
            )

    def _render_load_error(self, message: str) -> None:
        if not self.is_mounted:
            return
        self._render_summary(f"Error: {message}")
        self.notify(message, severity="error", title="No se pudo cargar la batalla")

    def _render_summary(self, text: str) -> None:
        self.query_one("#lbl-summary", Label).update(text)

    def action_dismiss_screen(self) -> None:
        self.dismiss()
