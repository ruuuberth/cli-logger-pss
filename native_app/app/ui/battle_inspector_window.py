from __future__ import annotations

from typing import Any

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


_DARK_STYLE = """
QMainWindow { background: #0f141b; }
QFrame#headerCard {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #0d4f69, stop:1 #2f7a89);
    border-radius: 12px;
    padding: 8px;
}
QLabel#titleLabel {
    color: #ecf9ff;
    font-size: 22px;
    font-weight: 700;
}
QLabel#subtitleLabel {
    color: #d5ecf5;
    font-size: 12px;
    font-weight: 500;
}
QFrame#statsCard {
    background: #151f2b;
    border: 1px solid #253245;
    border-radius: 10px;
    padding: 8px;
}
QFrame#panelCard {
    background: #141b26;
    border: 1px solid #253245;
    border-radius: 10px;
    padding: 8px;
}
QLabel#statsKey {
    color: #91a6be;
    font-size: 11px;
    font-weight: 600;
}
QLabel#statsValue {
    color: #edf5ff;
    font-size: 14px;
    font-weight: 700;
}
QLabel#panelTitle {
    color: #e6f3ff;
    font-size: 14px;
    font-weight: 700;
}
QPlainTextEdit {
    background: #0f1722;
    color: #d4e2f0;
    border: 1px solid #253245;
    border-radius: 8px;
    padding: 10px;
    font-family: 'DejaVu Sans Mono', 'Consolas', monospace;
    font-size: 12px;
}
QTableWidget {
    background: #0f1722;
    color: #d4e2f0;
    gridline-color: #253245;
    border: 1px solid #253245;
    border-radius: 8px;
}
QHeaderView::section {
    background: #1a2533;
    color: #c9ddf1;
    border: none;
    border-right: 1px solid #253245;
    border-bottom: 1px solid #253245;
    padding: 6px;
    font-weight: 600;
}
QPushButton {
    background: #1a2533;
    color: #d8e9fb;
    border: 1px solid #2c4662;
    border-radius: 8px;
    padding: 8px 10px;
    font-weight: 600;
}
QPushButton:hover { background: #213349; }
"""


class TableInspectorWindow(QMainWindow):
    def __init__(self, title: str, content: QWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(1180, 760)
        self.setStyleSheet(_DARK_STYLE)
        self.setCentralWidget(content)


class BattleInspectorWindow(QMainWindow):
    def __init__(self, detail: dict[str, Any], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.detail = detail
        self.child_inspectors: list[TableInspectorWindow] = []

        replay = detail.get("replay") or {}
        battle_id = replay.get("battle_id") or "-"
        self.setWindowTitle(f"Inspector Manager #{battle_id}")
        self.resize(980, 720)
        self.setStyleSheet(_DARK_STYLE)

        wrapper = QWidget(self)
        layout = QVBoxLayout()
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        header_card = self._build_header_card(replay)
        stats_card = self._build_stats_card(detail)
        summary_card = self._build_summary_card(detail)
        manager_card = self._build_manager_card()

        layout.addWidget(header_card)
        layout.addWidget(stats_card)
        layout.addWidget(summary_card)
        layout.addWidget(manager_card)
        wrapper.setLayout(layout)
        self.setCentralWidget(wrapper)

    def closeEvent(self, event: QCloseEvent) -> None:
        super().closeEvent(event)
        # Ensure the window is actually destroyed after user closes it.
        self.deleteLater()

    def _build_header_card(self, replay: dict[str, Any]) -> QFrame:
        battle_id = replay.get("battle_id") or "-"
        frame = QFrame()
        frame.setObjectName("headerCard")
        layout = QVBoxLayout()
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(3)
        title_label = QLabel(f"Batalla #{battle_id}")
        title_label.setObjectName("titleLabel")
        subtitle_label = QLabel(
            f"{replay.get('attacker_name') or '-'} vs {replay.get('defender_name') or '-'}"
        )
        subtitle_label.setObjectName("subtitleLabel")
        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)
        frame.setLayout(layout)
        return frame

    def _build_stats_card(self, detail: dict[str, Any]) -> QFrame:
        frame = QFrame()
        frame.setObjectName("statsCard")
        grid = QGridLayout()
        grid.setContentsMargins(10, 8, 10, 8)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(8)

        for idx, (label, value) in enumerate(self._build_stats_items(detail)):
            row = (idx // 3) * 2
            col = idx % 3
            key_label = QLabel(label)
            key_label.setObjectName("statsKey")
            val_label = QLabel(value)
            val_label.setObjectName("statsValue")
            grid.addWidget(key_label, row, col)
            grid.addWidget(val_label, row + 1, col)

        frame.setLayout(grid)
        return frame

    def _build_summary_card(self, detail: dict[str, Any]) -> QFrame:
        frame = QFrame()
        frame.setObjectName("panelCard")
        layout = QVBoxLayout()
        title = QLabel("Resumen")
        title.setObjectName("panelTitle")
        text = QPlainTextEdit()
        text.setReadOnly(True)
        text.setPlainText("\n".join(self._build_summary_lines(detail)))
        layout.addWidget(title)
        layout.addWidget(text)
        frame.setLayout(layout)
        return frame

    def _build_manager_card(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("panelCard")
        layout = QVBoxLayout()
        title = QLabel("Inspectores")
        title.setObjectName("panelTitle")

        buttons_row = QHBoxLayout()
        ships_btn = QPushButton("Inspector de Naves")
        rooms_btn = QPushButton("Inspector de Salas")
        characters_btn = QPushButton("Inspector de Tripulacion")
        commands_btn = QPushButton("Inspector de Comandos")

        ships_btn.clicked.connect(self.open_ships_inspector)
        rooms_btn.clicked.connect(self.open_rooms_inspector)
        characters_btn.clicked.connect(self.open_characters_inspector)
        commands_btn.clicked.connect(self.open_commands_inspector)

        buttons_row.addWidget(ships_btn)
        buttons_row.addWidget(rooms_btn)
        buttons_row.addWidget(characters_btn)
        buttons_row.addWidget(commands_btn)

        help_text = QLabel(
            "Este inspector administra vistas enfocadas. Abre una por tabla para trabajar sin ruido visual."
        )
        help_text.setObjectName("statsKey")

        layout.addWidget(title)
        layout.addLayout(buttons_row)
        layout.addWidget(help_text)
        frame.setLayout(layout)
        return frame

    def open_ships_inspector(self) -> None:
        widget = self._build_split_side_widget(
            "Atacante",
            self._build_ship_info_table(
                self._filter_by_side(self.detail.get("ships") or [], "attacker"),
                side_name="attacker",
            ),
            None,
            "Defensor",
            self._build_ship_info_table(
                self._filter_by_side(self.detail.get("ships") or [], "defender"),
                side_name="defender",
            ),
            None,
            "Nave",
            None,
        )
        self._open_child("Inspector de Naves", widget)

    def open_rooms_inspector(self) -> None:
        widget = self._build_split_side_widget(
            "Atacante",
            self._build_rooms_table(self._filter_by_side(self.detail.get("rooms") or [], "attacker"), include_side=False),
            None,
            "Defensor",
            self._build_rooms_table(self._filter_by_side(self.detail.get("rooms") or [], "defender"), include_side=False),
            None,
            "Salas",
            None,
        )
        self._open_child("Inspector de Salas", widget)

    def open_characters_inspector(self) -> None:
        widget = self._build_split_side_widget(
            "Atacante",
            self._build_characters_table(self._filter_by_side(self.detail.get("characters") or [], "attacker"), include_side=False),
            None,
            "Defensor",
            self._build_characters_table(self._filter_by_side(self.detail.get("characters") or [], "defender"), include_side=False),
            None,
            "Tripulacion",
            None,
        )
        self._open_child("Inspector de Tripulacion", widget)

    def open_commands_inspector(self) -> None:
        wrapper = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        title = QLabel("Comandos")
        title.setObjectName("panelTitle")
        layout.addWidget(title)
        layout.addWidget(self._build_commands_table(self.detail.get("commands") or []))
        wrapper.setLayout(layout)
        self._open_child("Inspector de Comandos", wrapper)

    def _open_child(self, title: str, content: QWidget) -> None:
        window = TableInspectorWindow(title, content, self)
        self.child_inspectors.append(window)
        window.destroyed.connect(lambda *_: self._remove_child(window))
        window.show()

    def _remove_child(self, window: TableInspectorWindow) -> None:
        if window in self.child_inspectors:
            self.child_inspectors.remove(window)

    def _build_split_side_widget(
        self,
        left_title: str,
        left_primary: QTableWidget,
        left_secondary: QTableWidget | None,
        right_title: str,
        right_primary: QTableWidget,
        right_secondary: QTableWidget | None,
        primary_label: str,
        secondary_label: str | None,
    ) -> QWidget:
        wrapper = QWidget()
        root = QHBoxLayout()
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        left = self._build_side_card(left_title, left_primary, left_secondary, primary_label, secondary_label)
        right = self._build_side_card(right_title, right_primary, right_secondary, primary_label, secondary_label)
        root.addWidget(left)
        root.addWidget(right)
        wrapper.setLayout(root)
        return wrapper

    def _build_side_card(
        self,
        title: str,
        primary: QTableWidget,
        secondary: QTableWidget | None,
        primary_label: str,
        secondary_label: str | None,
    ) -> QFrame:
        card = QFrame()
        card.setObjectName("panelCard")
        layout = QVBoxLayout()
        layout.setSpacing(6)

        title_label = QLabel(title)
        title_label.setObjectName("panelTitle")
        layout.addWidget(title_label)

        primary_title = QLabel(primary_label)
        primary_title.setObjectName("statsKey")
        layout.addWidget(primary_title)
        layout.addWidget(primary)

        if secondary is not None and secondary_label is not None:
            secondary_title = QLabel(secondary_label)
            secondary_title.setObjectName("statsKey")
            layout.addWidget(secondary_title)
            layout.addWidget(secondary)

        card.setLayout(layout)
        return card

    def _build_stats_items(self, detail: dict[str, Any]) -> list[tuple[str, str]]:
        replay = detail.get("replay") or {}
        captured_at = str(replay.get("captured_at") or "-")
        return [
            ("Hora", captured_at[:19].replace("T", " ")),
            ("Resultado", str(replay.get("outcome_type") or "-")),
            ("BattleId", str(replay.get("battle_id") or "-")),
            ("Copas Win/Lose", f"{replay.get('win_trophy_result') or 0} / {replay.get('lose_trophy_result') or 0}"),
            ("Mineral Win/Lose", f"{replay.get('win_minerals_result') or 0} / {replay.get('lose_minerals_result') or 0}"),
            ("Gas Win/Lose", f"{replay.get('win_gas_result') or 0} / {replay.get('lose_gas_result') or 0}"),
        ]

    def _build_summary_lines(self, detail: dict[str, Any]) -> list[str]:
        replay = detail.get("replay") or {}
        captured_at = str(replay.get("captured_at") or "-")
        lines = [
            f"Batalla: {replay.get('battle_id') or '-'}",
            f"Hora: {captured_at[:19].replace('T', ' ')}",
            f"Atacante: {replay.get('attacker_name') or '-'}",
            f"Defensor: {replay.get('defender_name') or '-'}",
            f"Resultado: {replay.get('outcome_type') or '-'}",
            "Botin/Copas: "
            f"WIN M={replay.get('win_minerals_result') or 0} G={replay.get('win_gas_result') or 0} T={replay.get('win_trophy_result') or 0} | "
            f"LOSE M={replay.get('lose_minerals_result') or 0} G={replay.get('lose_gas_result') or 0} T={replay.get('lose_trophy_result') or 0}",
        ]
        lines.extend(self._build_user_attributes_summary("Atacante", replay.get("attacker_user_attributes_json")))
        lines.extend(self._build_user_attributes_summary("Defensor", replay.get("defender_user_attributes_json")))
        return lines

    def _build_user_attributes_summary(self, label: str, attrs: Any) -> list[str]:
        if not isinstance(attrs, dict) or not attrs:
            return [f"{label} attributes: -"]
        lines = [f"{label} attributes:"]
        for key in sorted(attrs.keys()):
            value = attrs.get(key)
            if value is None or str(value).strip() == "":
                continue
            lines.append(f"  - {key}: {value}")
        return lines

    def _filter_by_side(self, rows: list[dict[str, Any]], side: str) -> list[dict[str, Any]]:
        return [row for row in rows if str(row.get("side") or "").lower() == side]

    def _build_ships_table(self, ships: list[dict[str, Any]], *, include_side: bool = True) -> QTableWidget:
        headers = ["Nave", "Nivel", "PowerScore", "HP"]
        if include_side:
            headers = ["Side"] + headers
        table = QTableWidget(len(ships), len(headers))
        table.setHorizontalHeaderLabels(headers)
        for idx, ship in enumerate(ships):
            translated_name = str(ship.get("ship_design_name") or "").strip()
            display_name = translated_name or "Sin traduccion"
            values = [
                str(ship.get("side") or "-"),
                display_name,
                str(ship.get("ship_level") or "-"),
                str(ship.get("power_score") or "-"),
                str(ship.get("hp") or "-"),
            ]
            if not include_side:
                values = values[1:]
            for col, value in enumerate(values):
                table.setItem(idx, col, QTableWidgetItem(value))
        table.horizontalHeader().setStretchLastSection(True)
        table.setAlternatingRowColors(True)
        return table

    def _build_ship_attributes_table(self, ships: list[dict[str, Any]]) -> QTableWidget:
        excluded_keys = {
            "BrightnessValue",
            "FromStarSystemId",
            "HueValue",
            "NextStarSystemId",
            "OriginNextStarSystemId",
            "OriginStarSystemId",
            "OriginalRaceId",
            "SalvageArgument",
            "SaturationValue",
            "SkinOpacityValue",
            "SkinItemDesignId",
            "UpgradeShipDesignId",
            "StickerString",
            "StatusStartDate",
            "StarSystemId",
            "StarSystemArrivalDate",
            "UpgradeStartDate",
            "UpdateDate",
            "Shield",
        }
        # Already represented in main ship table.
        repeated_keys = {
            "ShipId",
            "ShipDesignId",
            "ShipName",
            "ShipLevel",
            "PowerScore",
            "Hp",
            "ShipStatus",
        }
        rows: list[tuple[str, str]] = []
        for ship in ships:
            attrs = ship.get("ship_attributes_json")
            if not isinstance(attrs, dict):
                continue
            for key in sorted(attrs.keys()):
                key_text = str(key)
                if key_text in excluded_keys or key_text in repeated_keys:
                    continue
                value = attrs.get(key)
                if value is None or str(value).strip() == "":
                    continue
                rows.append((key_text, str(value)))

        table = QTableWidget(len(rows), 2)
        table.setHorizontalHeaderLabels(["Attribute", "Value"])
        for idx, (key, value) in enumerate(rows):
            table.setItem(idx, 0, QTableWidgetItem(key))
            table.setItem(idx, 1, QTableWidgetItem(value))
        table.horizontalHeader().setStretchLastSection(True)
        table.setAlternatingRowColors(True)
        return table

    def _build_ship_info_table(
        self,
        ships: list[dict[str, Any]],
        *,
        side_name: str,
    ) -> QTableWidget:
        rows: list[tuple[str, str]] = []
        if not ships:
            rows.append(("Nave", "Sin traduccion"))
            rows.append(("missing_ship_xml", "True"))

        for idx, ship in enumerate(ships, start=1):
            translated_name = str(ship.get("ship_design_name") or "").strip()
            display_name = translated_name or "Sin traduccion"
            rows.append((f"Nave {idx}", display_name))
            rows.append(("Nivel", str(ship.get("ship_level") or "-")))
            rows.append(("PowerScore", str(ship.get("power_score") or "-")))
            rows.append(("HP", str(ship.get("hp") or "-")))

            attrs_table = self._build_ship_attributes_table([ship])
            for attr_row in range(attrs_table.rowCount()):
                key_item = attrs_table.item(attr_row, 0)
                value_item = attrs_table.item(attr_row, 1)
                key_text = key_item.text() if key_item else "-"
                value_text = value_item.text() if value_item else "-"
                rows.append((key_text, value_text))

        if ships and not any(key == "missing_ship_xml" for key, _ in rows):
            # Garantiza trazabilidad visual por lado en casos normales.
            rows.append(("side", side_name))

        table = QTableWidget(len(rows), 2)
        table.setHorizontalHeaderLabels(["Attribute", "Value"])
        for row_idx, (key, value) in enumerate(rows):
            table.setItem(row_idx, 0, QTableWidgetItem(key))
            table.setItem(row_idx, 1, QTableWidgetItem(value))
        table.horizontalHeader().setStretchLastSection(True)
        table.setAlternatingRowColors(True)
        return table

    def _build_rooms_table(self, rooms: list[dict[str, Any]], *, include_side: bool = True) -> QTableWidget:
        base_headers = ["Diseno", "Fila", "Columna"]
        dynamic_headers = self._collect_attribute_keys(
            rooms,
            "room_attributes_json",
            exclude_keys={
                "Row",
                "row",
                "Column",
                "column",
                "RoomStatus",
                "Status",
                "CapacityUsed",
                "Capacity Used",
                "ConstructionStart",
                "ConstrucionStart",
                "ManufactureStart",
                "Manufacture Start",
                "ManufactureString",
                "Manufactured",
                "SalvageString",
                "ShipId",
                "ShipID",
            },
        )
        headers = (["Side"] if include_side else []) + base_headers + dynamic_headers
        table = QTableWidget(len(rooms), len(headers))
        table.setHorizontalHeaderLabels(headers)
        for idx, room in enumerate(rooms):
            translated_name = str(room.get("room_design_name") or "").strip() or "Sin traduccion"
            values = [
                str(room.get("side") or "-"),
                translated_name,
                str(room.get("row") or "-"),
                str(room.get("column") or "-"),
            ]
            if not include_side:
                values = values[1:]
            attrs = room.get("room_attributes_json")
            if not isinstance(attrs, dict):
                attrs = {}
            for key in dynamic_headers:
                value = attrs.get(key)
                if value is None or str(value).strip() == "":
                    values.append("-")
                else:
                    values.append(str(value))
            for col, value in enumerate(values):
                table.setItem(idx, col, QTableWidgetItem(value))
        table.horizontalHeader().setStretchLastSection(True)
        table.setAlternatingRowColors(True)
        return table

    def _build_characters_table(
        self, characters: list[dict[str, Any]], *, include_side: bool = True
    ) -> QTableWidget:
        base_headers = ["Nombre", "Diseno", "Nivel", "XP"]
        dynamic_headers = self._collect_attribute_keys(characters, "character_attributes_json")
        headers = (["Side"] if include_side else []) + base_headers + dynamic_headers
        table = QTableWidget(len(characters), len(headers))
        table.setHorizontalHeaderLabels(headers)
        for idx, character in enumerate(characters):
            translated_name = str(character.get("character_design_name") or "").strip() or "Sin traduccion"
            values = [
                str(character.get("side") or "-"),
                str(character.get("character_name") or "-"),
                translated_name,
                str(character.get("level") or "-"),
                str(character.get("xp") or "-"),
            ]
            if not include_side:
                values = values[1:]
            attrs = character.get("character_attributes_json")
            if not isinstance(attrs, dict):
                attrs = {}
            for key in dynamic_headers:
                value = attrs.get(key)
                if value is None or str(value).strip() == "":
                    values.append("-")
                else:
                    values.append(str(value))
            for col, value in enumerate(values):
                table.setItem(idx, col, QTableWidgetItem(value))
        table.horizontalHeader().setStretchLastSection(True)
        table.setAlternatingRowColors(True)
        return table

    def _build_commands_table(self, commands: list[dict[str, Any]]) -> QTableWidget:
        table = QTableWidget(len(commands), 2)
        table.setHorizontalHeaderLabels(["Orden", "Comando"])
        for idx, command in enumerate(commands):
            order = command.get("command_order")
            table.setItem(idx, 0, QTableWidgetItem(str(order if order is not None else "-")))
            table.setItem(idx, 1, QTableWidgetItem(str(command.get("command_tag") or "-")))
        table.horizontalHeader().setStretchLastSection(True)
        table.setAlternatingRowColors(True)
        return table

    def _collect_attribute_keys(
        self,
        rows: list[dict[str, Any]],
        key_name: str,
        *,
        exclude_keys: set[str] | None = None,
    ) -> list[str]:
        keys: set[str] = set()
        exclude_keys = exclude_keys or set()
        for row in rows:
            attrs = row.get(key_name)
            if not isinstance(attrs, dict):
                continue
            for key in attrs.keys():
                key_text = str(key)
                if key_text in exclude_keys:
                    continue
                keys.add(key_text)
        return sorted(keys)
