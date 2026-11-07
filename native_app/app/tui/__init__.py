"""Interactive TUI for PSS Logger (issue #47).

Reuses the existing CLI services (ApiFlowCliService, CharacterCliService,
RoomCliService) and ApiFlowRuntime — no new application logic.
"""

from app.tui.app import PssTuiApp, run_tui

__all__ = ["PssTuiApp", "run_tui"]
