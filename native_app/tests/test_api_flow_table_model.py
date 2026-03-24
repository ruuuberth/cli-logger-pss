from __future__ import annotations

import sys
from types import ModuleType

try:
    from PySide6.QtCore import Qt  # noqa: F401
except (ModuleNotFoundError, ImportError):
    pyside6 = ModuleType("PySide6")
    qtcore = ModuleType("PySide6.QtCore")

    class _ModelIndex:
        def __init__(self, row: int = -1, column: int = -1) -> None:
            self._row = row
            self._column = column

        def isValid(self) -> bool:
            return self._row >= 0 and self._column >= 0

        def row(self) -> int:
            return self._row

        def column(self) -> int:
            return self._column

    class _AbstractTableModel:
        def beginResetModel(self) -> None:
            pass

        def endResetModel(self) -> None:
            pass

        def index(self, row: int, column: int):
            return _ModelIndex(row, column)

        def headerData(self, section, orientation, role):
            return None

    class _Qt:
        DisplayRole = 0
        EditRole = 1
        TextAlignmentRole = 2
        ToolTipRole = 3
        Horizontal = 1
        AlignCenter = 4
        Orientation = int

    qtcore.QAbstractTableModel = _AbstractTableModel
    qtcore.QModelIndex = _ModelIndex
    qtcore.Qt = _Qt
    pyside6.QtCore = qtcore
    sys.modules["PySide6"] = pyside6
    sys.modules["PySide6.QtCore"] = qtcore

from PySide6.QtCore import Qt

from app.services.api_flow_list_service import ApiFlowRowView
from app.ui.models.api_flow_table_model import ApiFlowTableModel


def test_table_model_exposes_rows_and_headers() -> None:
    model = ApiFlowTableModel()
    row = ApiFlowRowView(
        battle_replay_id=1,
        api_flow_event_id=2,
        captured_at_label="2026-02-20 10:00:00",
        attacker_label="(10)A",
        defender_label="(20)B",
        outcome_label="Win",
        loot_label="M 1/0 | G 2/0",
        trophy_delta_label="3/0",
        battle_id_label="77",
        h2h_label="A 3 | D 2 | U 1",
        h2h_tooltip="H2H: A vs B",
    )
    model.set_rows([row])

    assert model.rowCount() == 1
    assert model.columnCount() == 10
    index = model.index(0, 1)
    assert model.data(index) == "(10)A"
    assert model.headerData(7, 1) == "H2H"
    assert model.data(model.index(0, 7)) == "A 3 | D 2 | U 1"
    assert model.data(model.index(0, 7), Qt.ToolTipRole) == "H2H: A vs B"


def test_table_model_returns_action_labels() -> None:
    model = ApiFlowTableModel()
    row = ApiFlowRowView(
        battle_replay_id=1,
        api_flow_event_id=2,
        captured_at_label="-",
        attacker_label="-",
        defender_label="-",
        outcome_label="-",
        loot_label="-",
        trophy_delta_label="-",
        battle_id_label="-",
        h2h_label="-",
        h2h_tooltip="Sin datos H2H",
    )
    model.set_rows([row])
    assert model.data(model.index(0, 8)) == "Inspeccionar"
    assert model.data(model.index(0, 9)) == "Eliminar"
