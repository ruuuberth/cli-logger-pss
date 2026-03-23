from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class ApiFlowRuntimeBridge(QObject):
    state_changed = Signal(dict)
    startup_sync_finished = Signal(dict)
    stop_flush_finished = Signal(dict)
    events_flushed = Signal(dict)
