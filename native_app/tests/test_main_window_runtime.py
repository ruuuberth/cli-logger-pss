from __future__ import annotations

import sys
import pytest
from types import ModuleType, SimpleNamespace

pytest.skip("UI tests skipped after migration to CLI", allow_module_level=True)

try:
    from PySide6.QtCore import QObject as _QtObjectProbe  # noqa: F401
except (ModuleNotFoundError, ImportError):
    pyside6 = ModuleType("PySide6")
    qtcore = ModuleType("PySide6.QtCore")
    qtgui = ModuleType("PySide6.QtGui")
    qtwidgets = ModuleType("PySide6.QtWidgets")

    class _Dummy:
        def __init__(self, *args, **kwargs) -> None:
            pass

    class _Signal:
        def __init__(self, *args, **kwargs) -> None:
            self._callbacks = []

        def connect(self, callback, *args, **kwargs) -> None:
            self._callbacks.append(callback)

        def emit(self, *args, **kwargs) -> None:
            for callback in list(self._callbacks):
                callback(*args, **kwargs)

    def _slot(*args, **kwargs):
        def _decorator(fn):
            return fn

        return _decorator

    class _Timer:
        def __init__(self, *args, **kwargs) -> None:
            self.timeout = _Signal()

        def setInterval(self, *_args, **_kwargs) -> None:
            pass

        def start(self) -> None:
            pass

        def stop(self) -> None:
            pass

        def isActive(self) -> bool:
            return False

        @staticmethod
        def singleShot(_ms, callback) -> None:
            callback()

    qtcore.QObject = _Dummy
    qtcore.QEvent = _Dummy
    qtcore.QRect = _Dummy
    qtcore.QTimer = _Timer
    qtcore.Signal = _Signal
    qtcore.Slot = _slot
    qtcore.QModelIndex = _Dummy
    qtcore.QAbstractTableModel = _Dummy
    qtcore.Qt = SimpleNamespace(
        DisplayRole=0,
        EditRole=1,
        TextAlignmentRole=2,
        Horizontal=1,
        AlignCenter=4,
    )
    qtgui.QCloseEvent = _Dummy
    qtgui.QMouseEvent = _Dummy
    qtgui.QPainter = _Dummy
    qtwidgets.QApplication = _Dummy
    qtwidgets.QAbstractItemView = SimpleNamespace(SelectRows=1, SingleSelection=1)
    qtwidgets.QCheckBox = _Dummy
    qtwidgets.QFileDialog = _Dummy
    qtwidgets.QFrame = _Dummy
    qtwidgets.QGridLayout = _Dummy
    qtwidgets.QHBoxLayout = _Dummy
    qtwidgets.QLabel = _Dummy
    qtwidgets.QLineEdit = _Dummy
    qtwidgets.QMainWindow = _Dummy
    qtwidgets.QMessageBox = _Dummy
    qtwidgets.QPlainTextEdit = _Dummy
    qtwidgets.QPushButton = _Dummy
    qtwidgets.QSizePolicy = _Dummy
    qtwidgets.QStyle = SimpleNamespace(State_Enabled=1, State_MouseOver=2, CE_PushButton=3)
    qtwidgets.QStyleOptionButton = _Dummy
    qtwidgets.QStyledItemDelegate = _Dummy
    qtwidgets.QTableWidget = _Dummy
    qtwidgets.QTableWidgetItem = _Dummy
    qtwidgets.QTableView = _Dummy
    qtwidgets.QVBoxLayout = _Dummy
    qtwidgets.QWidget = _Dummy
    qtwidgets.QHeaderView = SimpleNamespace(ResizeToContents=1, Fixed=1, Interactive=2)
    pyside6.QtCore = qtcore
    pyside6.QtGui = qtgui
    pyside6.QtWidgets = qtwidgets
    sys.modules["PySide6"] = pyside6
    sys.modules["PySide6.QtCore"] = qtcore
    sys.modules["PySide6.QtGui"] = qtgui
    sys.modules["PySide6.QtWidgets"] = qtwidgets

from app.services.api_flow_runtime import ApiFlowRuntimeState
from app.ui.main_window import MainWindow


class _Label:
    def __init__(self) -> None:
        self.value = ""

    def setText(self, text: str) -> None:
        self.value = text


class _Button:
    def __init__(self) -> None:
        self.text = ""

    def setText(self, text: str) -> None:
        self.text = text


class _Timer:
    def __init__(self) -> None:
        self.started = False

    def isActive(self) -> bool:
        return self.started

    def start(self) -> None:
        self.started = True


def test_runtime_state_updates_visible_labels() -> None:
    window = object.__new__(MainWindow)
    window.api_flow_status_label = _Label()
    window.api_flow_sync_label = _Label()
    window.api_flow_counter_label = _Label()
    window.api_flow_session_label = _Label()
    window.api_flow_capture_button = _Button()
    window.api_flow_runtime = SimpleNamespace(is_capture_running=lambda: True)

    MainWindow._on_runtime_state_changed(
        window,
        {
            "capture_running": True,
            "capture_status": "Captura activa en 127.0.0.1:8080",
            "session_id": "abc",
            "session_host": "127.0.0.1",
            "session_port": 8080,
            "live_event_count": 5,
            "dropped_pending_events": 0,
            "pending_count": 1,
            "flush_failures": 0,
            "startup_sync_running": False,
            "startup_sync_status": "listo",
            "stop_flush_running": False,
        },
    )

    assert window.api_flow_status_label.value == "Estado: activo en 127.0.0.1:8080"
    assert window.api_flow_sync_label.value == "Historial: listo"
    assert window.api_flow_counter_label.value == "Eventos (sesion): 5"
    assert window.api_flow_session_label.value == "Sesion: abc"
    assert window.api_flow_capture_button.text == "Detener captura"


def test_runtime_error_status_is_not_hidden_while_running() -> None:
    window = object.__new__(MainWindow)
    window.api_flow_status_label = _Label()
    window.api_flow_sync_label = _Label()
    window.api_flow_counter_label = _Label()
    window.api_flow_session_label = _Label()
    window.api_flow_capture_button = _Button()
    window.api_flow_runtime = SimpleNamespace(is_capture_running=lambda: True)

    MainWindow._on_runtime_state_changed(
        window,
        {
            "capture_running": True,
            "capture_status": "error de persistencia, reintentos=1, pendientes=2",
            "session_id": "abc",
            "session_host": "127.0.0.1",
            "session_port": 8080,
            "live_event_count": 5,
            "dropped_pending_events": 0,
            "pending_count": 2,
            "flush_failures": 1,
            "startup_sync_running": False,
            "startup_sync_status": "listo",
            "stop_flush_running": False,
        },
    )

    assert window.api_flow_status_label.value == "Estado: error de persistencia, reintentos=1, pendientes=2"


def test_capture_error_code_and_friendly_message_helpers() -> None:
    window = object.__new__(MainWindow)
    code = MainWindow._extract_capture_error_code(window, "[capture_proxy_missing] missing proxy")
    assert code == "capture_proxy_missing"
    friendly = MainWindow._friendly_capture_error_message(window, code, "raw")
    assert "No se encontró mitmproxy" in friendly


def test_start_capture_failure_updates_runtime_status() -> None:
    class _Runtime:
        def __init__(self) -> None:
            self.error = ""

        def start_capture(self) -> None:
            raise RuntimeError("[capture_proxy_missing] missing")

        def set_capture_error(self, message: str) -> None:
            self.error = message

    window = object.__new__(MainWindow)
    window.api_flow_runtime = _Runtime()
    window.api_flow_status_label = _Label()
    window.api_flow_flush_timer = _Timer()

    MainWindow.start_api_flow_capture(window, user_initiated=False)

    assert window.api_flow_runtime.error == "captura no disponible (capture_proxy_missing)"
    assert window.api_flow_status_label.value == "Estado: captura no disponible (capture_proxy_missing)"
