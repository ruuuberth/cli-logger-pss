from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt


class SimpleTableModel(QAbstractTableModel):
    def __init__(self, headers: list[str] | None = None, rows: list[list[str]] | None = None) -> None:
        super().__init__()
        self._headers = list(headers or [])
        self._rows = [list(row) for row in (rows or [])]

    def set_data(self, headers: list[str], rows: list[list[str]]) -> None:
        self.beginResetModel()
        self._headers = list(headers)
        self._rows = [list(row) for row in rows]
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._headers)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid():
            return None
        if role in {Qt.DisplayRole, Qt.EditRole}:
            try:
                return self._rows[index.row()][index.column()]
            except Exception:
                return ""
        if role == Qt.TextAlignmentRole:
            value = self._rows[index.row()][index.column()]
            if value in {"Inspeccionar", "Eliminar", "Inspector IA", "Equipo"}:
                return int(Qt.AlignCenter)
        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal and 0 <= section < len(self._headers):
            return self._headers[section]
        return super().headerData(section, orientation, role)
