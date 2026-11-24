"""Tests for the TUI entry point and app shell (issue #47).

Foundation slice: the app mounts, the services are injectable, and
`pss-native --tui` dispatches. Data rendering (battle explorer, detail
screen, live capture state) is added in the follow-up PRs.
"""

from __future__ import annotations

import asyncio

from app.dto.api_flow_dto import ApiFlowRowDTO  # noqa: F401  (import sanity)
from app.tui import run_tui
from app.tui.app import PssTuiApp


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


class TestTuiShellMounts:
    def test_mount_renders_dashboard_labels(self) -> None:
        from textual.widgets import Label

        async def scenario() -> None:
            app = PssTuiApp()
            async with app.run_test():
                for label_id in ("#lbl-capture", "#lbl-events", "#lbl-status"):
                    assert app.query_one(label_id, Label) is not None

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
