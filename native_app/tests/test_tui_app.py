"""Tests for the TUI entry point and app shell (issue #47).

Foundation slice: the app mounts, the services are injectable, and
`pss-native --tui` dispatches. Explorer rendering, the detail screen and
the live capture state are added in the follow-up PRs.
"""

from __future__ import annotations

import asyncio

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

    def __init__(self, total: int = 3) -> None:
        self._total = total
        self.calls: list[dict] = []

    def query_events(self, search="", page=0, page_size=20, **kwargs):
        self.calls.append({"search": search, "page": page, "page_size": page_size})
        rows = [_row()] if self._total else []
        return ApiFlowPageDTO(total=self._total, page=page, max_page=0, rows=rows)


def _label_text(label) -> str:
    content = label.content
    return getattr(content, "plain", str(content))


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
        from textual.widgets import DataTable

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
