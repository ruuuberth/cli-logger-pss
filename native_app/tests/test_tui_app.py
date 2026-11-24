"""Tests for the TUI entry point, explorer, detail screen and dashboard (#47).

Covers the app as the user drives it: headless mount through Textual's
Pilot, real key presses, and the service boundary stubbed (no DB in tests).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from textual.widgets import DataTable, Input, Label

from app.dto.api_flow_dto import ApiFlowPageDTO, ApiFlowRowDTO
from app.tui import run_tui
from app.tui.app import PAGE_SIZE, PssTuiApp


def _row() -> ApiFlowRowDTO:
    return ApiFlowRowDTO(
        battle_replay_id=1,
        api_flow_event_id=None,
        captured_at_label="2026-01-01 00:00:00",
        attacker_label="(100)A",
        defender_label="(90)D",
        outcome_label="win",
        loot_label="M 1/0 | G 2/0",
        trophy_delta_label="10/0",
        battle_id_label="B1",
        h2h_label="",
        h2h_tooltip="",
    )


class _FakeService:
    """Stands in for ApiFlowCliService at the TUI boundary."""

    def __init__(self, total: int = 3, detail: dict | None = None) -> None:
        self._total = total
        self.calls: list[dict] = []
        self.detail = detail

    def query_events(self, search="", page=0, page_size=20, **kwargs):
        self.calls.append({"search": search, "page": page, "page_size": page_size})
        rows = [_row()] if self._total else []
        return ApiFlowPageDTO(total=self._total, page=page, max_page=0, rows=rows)

    def get_battle_detail(self, battle_replay_id: int) -> dict | None:
        return self.detail


class _FakeInspectors:
    def list_rooms(self, battle_replay_id: int) -> list[dict]:
        return [
            {
                "id": 9,
                "side": "attacker",
                "design_name": "Bridge",
                "row": 1,
                "column": 2,
            }
        ]

    def list_characters(self, battle_replay_id: int) -> list[dict]:
        return [{"id": 7, "side": "attacker", "name": "Crew", "level": 5}]


def _label_text(label) -> str:
    content = label.content
    return getattr(content, "plain", str(content))


@dataclass(frozen=True)
class _FakeRuntimeState:
    capture_running: bool = False
    capture_status: str = "idle"
    session_id: str = "-"
    session_host: str = "127.0.0.1"
    session_port: int | None = 8081
    live_event_count: int = 0
    dropped_pending_events: int = 0
    pending_count: int = 0
    flush_failures: int = 0
    startup_sync_running: bool = False
    startup_sync_status: str = ""
    stop_flush_running: bool = False


class _FakeRuntime:
    def __init__(self) -> None:
        self.toggled = 0

    def snapshot_state(self) -> _FakeRuntimeState:
        return _FakeRuntimeState()

    def toggle_capture(self) -> None:
        self.toggled += 1


class TestPssTuiAppWiring:
    def test_defaults_use_real_services(self) -> None:
        app = PssTuiApp()
        assert app.service is not None
        assert app.characters is not None
        assert app.rooms is not None

    def test_injects_fake_services(self) -> None:
        service = object()
        app = PssTuiApp(cli_service=service)
        assert app.service is service


class TestTuiExplorer:
    def test_mount_renders_rows_and_labels(self) -> None:
        service = _FakeService(total=1)

        async def scenario() -> None:
            app = PssTuiApp(cli_service=service)
            async with app.run_test() as pilot:
                await app.workers.wait_for_complete()
                await pilot.pause()
                table = app.query_one("#table-battles", DataTable)
                assert table.row_count == 1
                assert service.calls[0] == {
                    "search": "",
                    "page": 0,
                    "page_size": PAGE_SIZE,
                }

        asyncio.run(scenario())

    def test_next_page_binding_queries_page_1(self) -> None:
        service = _FakeService(total=PAGE_SIZE * 2)

        async def scenario() -> None:
            app = PssTuiApp(cli_service=service)
            async with app.run_test() as pilot:
                await app.workers.wait_for_complete()
                await pilot.pause()
                await pilot.press("n")
                await app.workers.wait_for_complete()
                await pilot.pause()
                assert app.page == 1
                assert service.calls[-1]["page"] == 1

        asyncio.run(scenario())


class TestBattleDetailScreen:
    def test_enter_opens_detail_and_escape_dismisses(self) -> None:
        detail = {
            "replay": {
                "battle_id": "B1",
                "captured_at": "2026-01-01",
                "outcome_type": "win",
            },
            "ships": [{"id": 1, "side": "attacker", "ship_design_name": "Falcon"}],
            "rooms": [{"id": 2, "side": "attacker", "room_design_name": "Bridge"}],
            "characters": [{"id": 3, "side": "attacker", "character_name": "Crew"}],
        }
        service = _FakeService(total=1, detail=detail)

        async def scenario() -> None:
            app = PssTuiApp(
                cli_service=service,
                character_service=_FakeInspectors(),
                room_service=_FakeInspectors(),
            )
            async with app.run_test() as pilot:
                await app.workers.wait_for_complete()
                await pilot.pause()
                await pilot.press("enter")
                await pilot.pause()

                from app.tui.screens import BattleDetailScreen

                screen = app.screen
                assert isinstance(screen, BattleDetailScreen)
                await app.workers.wait_for_complete()
                await pilot.pause()
                assert screen.query_one("#table-ships", DataTable).row_count == 1
                assert screen.query_one("#table-rooms", DataTable).row_count == 1
                assert screen.query_one("#table-crew", DataTable).row_count == 1
                assert "B1" in _label_text(screen.query_one("#lbl-summary"))

                await pilot.press("escape")
                await pilot.pause()
                assert not isinstance(app.screen, BattleDetailScreen)

        asyncio.run(scenario())


class _BrokenService:
    def query_events(self, *args, **kwargs):
        raise RuntimeError("db caída")


def _runtime(runtime: _FakeRuntime) -> Any:
    return runtime


class TestTuiDashboardAndSearch:
    def test_empty_database_shows_status_message(self) -> None:
        async def scenario() -> None:
            app = PssTuiApp(cli_service=_FakeService(total=0))
            async with app.run_test() as pilot:
                await app.workers.wait_for_complete()
                await pilot.pause()
                assert "Sin batallas" in _label_text(
                    app.query_one("#lbl-status", Label)
                )

        asyncio.run(scenario())

    def test_service_error_is_shown(self) -> None:
        async def scenario() -> None:
            app = PssTuiApp(cli_service=_BrokenService())
            async with app.run_test() as pilot:
                await app.workers.wait_for_complete()
                await pilot.pause()
                assert "db caída" in _label_text(app.query_one("#lbl-status", Label))

        asyncio.run(scenario())

    def test_search_submit_resets_page_and_filters(self) -> None:
        service = _FakeService(total=PAGE_SIZE * 3)

        async def scenario() -> None:
            app = PssTuiApp(cli_service=service)
            async with app.run_test() as pilot:
                await app.workers.wait_for_complete()
                await pilot.pause()
                await pilot.press("n")
                await app.workers.wait_for_complete()
                await pilot.pause()

                await pilot.press("slash")
                search = app.query_one("#input-search", Input)
                assert search.has_focus
                search.value = "alpha"
                await pilot.press("enter")
                await app.workers.wait_for_complete()
                await pilot.pause()
                assert service.calls[-1]["search"] == "alpha"
                assert service.calls[-1]["page"] == 0
                assert app.page == 0

        asyncio.run(scenario())

    def test_toggle_capture_uses_worker_and_updates_dashboard(self) -> None:
        runtime = _FakeRuntime()

        async def scenario() -> None:
            app = PssTuiApp(
                capture_runtime=_runtime(runtime), cli_service=_FakeService()
            )
            async with app.run_test() as pilot:
                await app.workers.wait_for_complete()
                await pilot.pause()
                assert "DETENIDA" in _label_text(app.query_one("#lbl-capture", Label))
                await pilot.press("s")
                await app.workers.wait_for_complete()
                await pilot.pause()
                assert runtime.toggled == 1

        asyncio.run(scenario())


class TestTuiEntryPoint:
    def test_run_tui_callable_with_runtime(self) -> None:
        assert callable(run_tui)

    def test_main_dispatches_tui_flag(self, monkeypatch) -> None:
        import sys

        import app.main as main_module

        monkeypatch.setattr(sys, "argv", ["pss-native", "--tui"])
        called = {}

        def fake_run_tui() -> int:
            called["yes"] = True
            return 0

        monkeypatch.setattr(main_module, "_run_tui", fake_run_tui)
        assert main_module.main() == 0
        assert called.get("yes") is True
