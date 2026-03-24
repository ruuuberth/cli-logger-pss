from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace

try:
    from PySide6.QtCore import QEvent  # noqa: F401
except (ModuleNotFoundError, ImportError):
    pyside6 = ModuleType("PySide6")
    qtcore = ModuleType("PySide6.QtCore")
    qtgui = ModuleType("PySide6.QtGui")
    qtwidgets = ModuleType("PySide6.QtWidgets")

    class _Signal:
        def __init__(self, *args, **kwargs) -> None:
            self._callbacks = []

        def connect(self, callback, *args, **kwargs) -> None:
            self._callbacks.append(callback)

        def emit(self, *args, **kwargs) -> None:
            for callback in list(self._callbacks):
                callback(*args, **kwargs)

    class _Delegate:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def editorEvent(self, *args, **kwargs) -> bool:
            return False

    class _Point:
        def __init__(self, x: int = 0, y: int = 0) -> None:
            self.x = x
            self.y = y

    class _Rect:
        def __init__(self, left: int = 0, top: int = 0, right: int = 100, bottom: int = 30) -> None:
            self.left = left
            self.top = top
            self.right = right
            self.bottom = bottom

        def adjusted(self, dx1: int, dy1: int, dx2: int, dy2: int):
            return _Rect(self.left + dx1, self.top + dy1, self.right + dx2, self.bottom + dy2)

        def contains(self, _point) -> bool:
            return True

    class _MouseEvent:
        def type(self) -> int:
            return 1

        def position(self):
            return SimpleNamespace(toPoint=lambda: _Point())

    qtcore.QEvent = SimpleNamespace(MouseButtonRelease=1)
    qtcore.QRect = _Rect
    qtcore.Signal = _Signal
    qtgui.QMouseEvent = _MouseEvent
    qtgui.QPainter = object
    qtwidgets.QApplication = SimpleNamespace(style=lambda: SimpleNamespace(drawControl=lambda *args, **kwargs: None))
    qtwidgets.QStyle = SimpleNamespace(State_Enabled=1, State_MouseOver=2, CE_PushButton=3)
    qtwidgets.QStyleOptionButton = type("QStyleOptionButton", (), {})
    qtwidgets.QStyledItemDelegate = _Delegate
    pyside6.QtCore = qtcore
    pyside6.QtGui = qtgui
    pyside6.QtWidgets = qtwidgets
    sys.modules["PySide6"] = pyside6
    sys.modules["PySide6.QtCore"] = qtcore
    sys.modules["PySide6.QtGui"] = qtgui
    sys.modules["PySide6.QtWidgets"] = qtwidgets

from PySide6.QtGui import QMouseEvent

import app.ui.delegates.row_action_delegate as delegate_module
from app.ui.delegates.row_action_delegate import RowActionDelegate


class _Index:
    def __init__(self, row: int, column: int) -> None:
        self._row = row
        self._column = column

    def column(self) -> int:
        return self._column

    def row(self) -> int:
        return self._row

    def data(self):
        return "Inspeccionar"


def test_delegate_emits_inspect_for_action_column() -> None:
    delegate_module.QEvent.MouseButtonRelease = 1
    delegate = RowActionDelegate(action_map={8: "inspect", 9: "delete"})
    seen: list[int] = []
    delegate.inspect_requested.connect(seen.append)
    option = SimpleNamespace(rect=SimpleNamespace(adjusted=lambda *args: SimpleNamespace(contains=lambda _p: True)))

    class _Event(QMouseEvent):
        def type(self):
            return 1

        def position(self):
            return SimpleNamespace(toPoint=lambda: object())

    event = _Event()

    handled = delegate.editorEvent(event, None, option, _Index(3, 8))

    assert handled is True
    assert seen == [3]


def test_delegate_does_not_handle_h2h_column() -> None:
    delegate_module.QEvent.MouseButtonRelease = 1
    delegate = RowActionDelegate(action_map={8: "inspect", 9: "delete"})
    option = SimpleNamespace(rect=SimpleNamespace(adjusted=lambda *args: SimpleNamespace(contains=lambda _p: True)))

    class _Event(QMouseEvent):
        def type(self):
            return 1

        def position(self):
            return SimpleNamespace(toPoint=lambda: object())

    handled = delegate.editorEvent(_Event(), None, option, _Index(1, 7))
    assert handled is False
