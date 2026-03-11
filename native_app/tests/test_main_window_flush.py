from __future__ import annotations

import sys
from types import ModuleType
from types import MethodType, SimpleNamespace

try:
    from PySide6.QtCore import QObject as _QtObjectProbe  # noqa: F401
except ModuleNotFoundError:
    pyside6 = ModuleType("PySide6")
    qtcore = ModuleType("PySide6.QtCore")
    qtgui = ModuleType("PySide6.QtGui")
    qtwidgets = ModuleType("PySide6.QtWidgets")

    class _Dummy:
        def __init__(self, *args, **kwargs) -> None:
            pass

    class _Signal:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def connect(self, *args, **kwargs) -> None:
            pass

        def emit(self, *args, **kwargs) -> None:
            pass

    def _slot(*args, **kwargs):
        def _decorator(fn):
            return fn

        return _decorator

    qtcore.QObject = _Dummy
    qtcore.QTimer = _Dummy
    qtcore.Signal = _Signal
    qtcore.Slot = _slot
    qtgui.QCloseEvent = _Dummy

    qtwidgets.QAbstractItemView = _Dummy
    qtwidgets.QCheckBox = _Dummy
    qtwidgets.QComboBox = _Dummy
    qtwidgets.QFrame = _Dummy
    qtwidgets.QGridLayout = _Dummy
    qtwidgets.QHBoxLayout = _Dummy
    qtwidgets.QLabel = _Dummy
    qtwidgets.QLineEdit = _Dummy
    qtwidgets.QMainWindow = _Dummy
    qtwidgets.QMessageBox = _Dummy
    qtwidgets.QPlainTextEdit = _Dummy
    qtwidgets.QPushButton = _Dummy
    qtwidgets.QSpinBox = _Dummy
    qtwidgets.QTabWidget = _Dummy
    qtwidgets.QTableWidget = _Dummy
    qtwidgets.QTableWidgetItem = _Dummy
    qtwidgets.QVBoxLayout = _Dummy
    qtwidgets.QWidget = _Dummy

    pyside6.QtCore = qtcore
    pyside6.QtGui = qtgui
    pyside6.QtWidgets = qtwidgets
    sys.modules["PySide6"] = pyside6
    sys.modules["PySide6.QtCore"] = qtcore
    sys.modules["PySide6.QtGui"] = qtgui
    sys.modules["PySide6.QtWidgets"] = qtwidgets

from app.ui.main_window import MainWindow


class _DummyLabel:
    def __init__(self) -> None:
        self.value = ""

    def setText(self, text: str) -> None:
        self.value = text


class _Repo:
    def __init__(self, save_return: int) -> None:
        self.save_return = save_return
        self.saved_batches: list[list[dict]] = []
        self.purge_calls = 0

    def save_events(self, events: list[dict]) -> int:
        self.saved_batches.append(list(events))
        return self.save_return

    def purge(self, retention_days: int, max_db_mb: int) -> None:
        self.purge_calls += 1


def _build_window_like(repo: _Repo, pending: list[dict], *, max_pending: int = 10_000):
    obj = SimpleNamespace()
    obj.api_flow_repository = repo
    obj.api_flow_pending_events = list(pending)
    obj.api_flow_flush_failures = 0
    obj.api_flow_dropped_pending_events = 0
    obj.api_flow_last_capture_status = "captura activa"
    obj.api_flow_status_label = _DummyLabel()
    obj.API_FLOW_PENDING_MAX_EVENTS = max_pending
    obj._enforce_pending_limit = MethodType(MainWindow._enforce_pending_limit, obj)
    return obj


def test_flush_retries_when_save_fails() -> None:
    repo = _Repo(save_return=0)
    win = _build_window_like(repo, [{"id": 1}, {"id": 2}])

    MainWindow._flush_pending_events(win)

    assert [event["id"] for event in win.api_flow_pending_events] == [1, 2]
    assert win.api_flow_flush_failures == 1
    assert repo.purge_calls == 0
    assert "error de persistencia" in win.api_flow_status_label.value


def test_flush_requeues_partial_save() -> None:
    repo = _Repo(save_return=1)
    win = _build_window_like(repo, [{"id": 1}, {"id": 2}, {"id": 3}])

    MainWindow._flush_pending_events(win)

    assert [event["id"] for event in win.api_flow_pending_events] == [2, 3]
    assert win.api_flow_flush_failures == 1
    assert repo.purge_calls == 0


def test_flush_limits_backlog_when_retrying() -> None:
    repo = _Repo(save_return=0)
    win = _build_window_like(repo, [{"id": 1}, {"id": 2}, {"id": 3}, {"id": 4}, {"id": 5}], max_pending=3)

    MainWindow._flush_pending_events(win)

    assert [event["id"] for event in win.api_flow_pending_events] == [3, 4, 5]
    assert win.api_flow_dropped_pending_events == 2
    assert win.api_flow_flush_failures == 1
