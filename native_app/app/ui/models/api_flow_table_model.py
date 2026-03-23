from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from app.services.api_flow_list_service import ApiFlowRowView


class ApiFlowTableModel(QAbstractTableModel):
    HEADERS = [
        "Hora",
        "Atacante",
        "Defensor",
        "Resultado",
        "Botin",
        "Copas",
        "BattleId",
        "Inspector",
        "Eliminar",
    ]

    def __init__(self) -> None:
        super().__init__()
        self._rows: list[ApiFlowRowView] = []

    def set_rows(self, rows: list[ApiFlowRowView]) -> None:
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()

    def row_at(self, row: int) -> ApiFlowRowView | None:
        if row < 0 or row >= len(self._rows):
            return None
        return self._rows[row]

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self.HEADERS)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        if role in {Qt.DisplayRole, Qt.EditRole}:
            mapping = {
                0: row.captured_at_label,
                1: row.attacker_label,
                2: row.defender_label,
                3: row.outcome_label,
                4: row.loot_label,
                5: row.trophy_delta_label,
                6: row.battle_id_label,
                7: "Inspeccionar",
                8: "Eliminar",
            }
            return mapping.get(index.column(), "")
        if role == Qt.TextAlignmentRole and index.column() >= 7:
            return int(Qt.AlignCenter)
        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal and 0 <= section < len(self.HEADERS):
            return self.HEADERS[section]
        return super().headerData(section, orientation, role)
