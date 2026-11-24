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

    # table id -> (column headers, dict keys rendered per row)
    TABLES = (
        ("#table-ships", ("ID", "Lado", "Diseño"), ("id", "side", "ship_design_name")),
        (
            "#table-rooms",
            ("ID", "Lado", "Sala", "Posición"),
            ("id", "side", "design_name", "position"),
        ),
        (
            "#table-crew",
            ("ID", "Nombre", "Lado", "Nivel"),
            ("id", "name", "side", "level"),
        ),
    )

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
        for table_id, columns, _fields in self.TABLES:
            self.query_one(table_id, DataTable).add_columns(*columns)
        self.run_worker(self._load_detail, thread=True, exclusive=True, group="detail")

    def _load_detail(self) -> None:
        try:
            detail = self.service.get_battle_detail(self.battle_replay_id)
            if not detail:
                self.app.call_from_thread(
                    self._render_summary,
                    f"Batalla {self.battle_replay_id}: sin datos (¿aún no normalizada?)",
                )
                return
            ships = detail.get("ships") or []
            rooms = self.rooms.list_rooms(self.battle_replay_id)
            crew = self.characters.list_characters(self.battle_replay_id)
        except Exception as exc:
            self.app.call_from_thread(self._render_load_error, str(exc))
            return
        rooms = [
            {**room, "position": f"({room.get('row', '-')},{room.get('column', '-')})"}
            for room in rooms
        ]
        self.app.call_from_thread(self._render_detail, detail, ships, rooms, crew)

    def _render_detail(self, detail: dict | None, *groups: list[dict]) -> None:
        if not self.is_mounted:
            return
        replay = (detail or {}).get("replay") or {}
        self._render_summary(
            f"Batalla {replay.get('battle_id', self.battle_replay_id)}"
            f"  ·  capturada: {replay.get('captured_at') or '-'}"
            f"  ·  resultado: {replay.get('outcome_type') or '-'}"
        )
        for (table_id, _columns, fields), rows in zip(self.TABLES, groups):
            table = self.query_one(table_id, DataTable)
            table.clear()
            for row in rows:
                table.add_row(*(str(row.get(field) or "-") for field in fields))

    def _render_load_error(self, message: str) -> None:
        if not self.is_mounted:
            return
        self._render_summary(f"Error: {message}")
        self.notify(message, severity="error", title="No se pudo cargar la batalla")

    def _render_summary(self, text: str) -> None:
        self.query_one("#lbl-summary", Label).update(text)

    def action_dismiss_screen(self) -> None:
        self.dismiss()
