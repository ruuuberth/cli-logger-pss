from __future__ import annotations

from PySide6.QtCore import QEvent, QRect, Signal
from PySide6.QtGui import QMouseEvent, QPainter
from PySide6.QtWidgets import QApplication, QStyle, QStyleOptionButton, QStyledItemDelegate


class RowActionDelegate(QStyledItemDelegate):
    inspect_requested = Signal(int)
    delete_requested = Signal(int)

    def paint(self, painter: QPainter, option, index) -> None:
        if index.column() not in {7, 8}:
            super().paint(painter, option, index)
            return
        button = self._button_option(option.rect, str(index.data() or ""))
        button.state |= QStyle.State_Enabled
        if option.state & QStyle.State_MouseOver:
            button.state |= QStyle.State_MouseOver
        style = option.widget.style() if option.widget else QApplication.style()
        style.drawControl(QStyle.CE_PushButton, button, painter, option.widget)

    def editorEvent(self, event, model, option, index) -> bool:
        if index.column() not in {7, 8}:
            return super().editorEvent(event, model, option, index)
        if event.type() == QEvent.MouseButtonRelease and isinstance(event, QMouseEvent):
            if self._button_rect(option.rect).contains(event.position().toPoint()):
                if index.column() == 7:
                    self.inspect_requested.emit(index.row())
                else:
                    self.delete_requested.emit(index.row())
                return True
        return False

    def _button_option(self, rect: QRect, text: str) -> QStyleOptionButton:
        button = QStyleOptionButton()
        button.rect = self._button_rect(rect)
        button.text = text
        return button

    def _button_rect(self, rect: QRect) -> QRect:
        horizontal_margin = 6
        vertical_margin = 4
        return rect.adjusted(horizontal_margin, vertical_margin, -horizontal_margin, -vertical_margin)
