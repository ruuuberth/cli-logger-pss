from __future__ import annotations

import json
from typing import Any
from pathlib import Path

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QFrame,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.models.database import SessionLocal
from app.services.catalogo import CatalogoResolver
from app.services.character_inspector_resolver import CharacterInspectorResolver
from app.services.room_item_mapping import RoomItemMappingResolver
from app.ui.ui_theme import window_font_qss

_DARK_STYLE = """
""" + window_font_qss() + """
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
        self.catalog_base_dir = CatalogoResolver.default_base_dir()
        self.catalogo = CatalogoResolver(
            base_dir=self.catalog_base_dir,
            db_session_factory=SessionLocal,
            status_callback=self._on_catalog_status,
        )
        self.character_inspector = CharacterInspectorResolver(catalogo=self.catalogo)
        self.room_item_mapping = RoomItemMappingResolver(catalogo=self.catalogo)
        self.catalog_status_label: QLabel | None = None

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

        catalog_panel = self._build_catalog_panel()
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
        layout.addWidget(catalog_panel)
        layout.addLayout(buttons_row)
        layout.addWidget(help_text)
        frame.setLayout(layout)
        return frame

    def _build_catalog_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("panelCard")
        panel_layout = QVBoxLayout()
        panel_layout.setContentsMargins(8, 8, 8, 8)
        panel_layout.setSpacing(6)

        title = QLabel("Catalogos locales")
        title.setObjectName("statsKey")
        panel_layout.addWidget(title)

        row = QHBoxLayout()
        self.catalog_path_input = QLineEdit()
        self.catalog_path_input.setPlaceholderText("Ruta de Data/Prod")
        if self.catalog_base_dir:
            self.catalog_path_input.setText(str(self.catalog_base_dir))
        browse_btn = QPushButton("Buscar")
        browse_btn.clicked.connect(self._browse_catalog_dir)
        auto_btn = QPushButton("Auto-detectar")
        auto_btn.clicked.connect(self._auto_detect_catalog_dir)
        apply_btn = QPushButton("Aplicar")
        apply_btn.clicked.connect(self._apply_catalog_dir)

        row.addWidget(self.catalog_path_input)
        row.addWidget(browse_btn)
        row.addWidget(auto_btn)
        row.addWidget(apply_btn)
        panel_layout.addLayout(row)

        self.catalog_status_label = QLabel()
        self.catalog_status_label.setObjectName("statsKey")
        self._refresh_catalog_status()
        panel_layout.addWidget(self.catalog_status_label)

        panel.setLayout(panel_layout)
        return panel

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
        if self._has_room_actions(self.detail):
            wrapper = QWidget()
            layout = QVBoxLayout()
            layout.setContentsMargins(14, 14, 14, 14)
            layout.setSpacing(10)
            room_actions_btn = QPushButton("Inspector IA (Room Actions)")
            room_actions_btn.clicked.connect(lambda: self.open_room_actions_inspector(self.detail))
            layout.addWidget(room_actions_btn)
            layout.addWidget(widget)
            wrapper.setLayout(layout)
            self._open_child("Inspector de Naves", wrapper)
            return
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
            display_name = self.catalogo.resolve_design_name(
                ship.get("ship_design_id"),
                translated_name,
                "ship",
            )
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
        table.setAlternatingRowColors(True)
        self._configure_table(table)
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
        table.setAlternatingRowColors(True)
        self._configure_table(table)
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
            display_name = self.catalogo.resolve_design_name(
                ship.get("ship_design_id"),
                translated_name,
                "ship",
            )
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
        table.setAlternatingRowColors(True)
        self._configure_table(table)
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
                "RoomActionsNormalized",
                "RoomAction",
                "RoomActions",
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
            exclude_prefixes={"RoomActions.", "RoomAction."},
        )
        headers = (["Side"] if include_side else []) + base_headers + dynamic_headers + ["IA"]
        table = QTableWidget(len(rooms), len(headers))
        table.setHorizontalHeaderLabels(headers)
        fallback_actions = self._room_actions_from_cleaned(self.detail)
        for idx, room in enumerate(rooms):
            translated_name = str(room.get("room_design_name") or "").strip()
            display_name = self.catalogo.resolve_design_name(
                room.get("room_design_id"),
                translated_name,
                "room",
            )
            values = [
                str(room.get("side") or "-"),
                display_name,
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
            attrs = room.get("room_attributes_json")
            if not isinstance(attrs, dict):
                attrs = {}
            actions = self._room_actions_for_room(room, attrs, fallback_actions)
            if actions:
                btn = QPushButton("Inspector IA")
                self._configure_button(btn)
                btn.clicked.connect(lambda _, r=room: self.open_room_actions_inspector(self.detail, r))
                table.setCellWidget(idx, len(headers) - 1, btn)
        table.setAlternatingRowColors(True)
        self._configure_table(table)
        return table

    def _build_characters_table(
        self, characters: list[dict[str, Any]], *, include_side: bool = True
    ) -> QTableWidget:
        base_headers = [
            "Nombre",
            "Diseno",
            "Nivel",
            "XP",
            "Sala",
            "Stamina",
            "Fatiga",
            "Ataque",
            "Reparacion",
            "Pilotaje",
            "Ciencia",
            "Ingenieria",
            "Habilidad",
            "HP",
            "Arma",
            "Entrenamiento",
            "Equipo",
            "Inspector IA",
        ]
        headers = (["Side"] if include_side else []) + base_headers
        table = QTableWidget(len(characters), len(headers))
        table.setHorizontalHeaderLabels(headers)
        for idx, character in enumerate(characters):
            translated_name = str(character.get("character_design_name") or "").strip()
            display_name = self.catalogo.resolve_design_name(
                character.get("character_design_id"),
                translated_name,
                "character",
            )
            stats = self.character_inspector.get_character_stats_summary(character)
            values = [
                str(character.get("side") or "-"),
                str(character.get("character_name") or "-"),
                display_name,
                str(character.get("level") or "-"),
                str(character.get("xp") or "-"),
                stats.get("room_id", "-"),
                stats.get("stamina", "-"),
                stats.get("fatigue", "-"),
                stats.get("attack_improvement", "-"),
                stats.get("repair_improvement", "-"),
                stats.get("pilot_improvement", "-"),
                stats.get("science_improvement", "-"),
                stats.get("engine_improvement", "-"),
                stats.get("ability_improvement", "-"),
                stats.get("hp_improvement", "-"),
                stats.get("weapon_improvement", "-"),
                stats.get("training", "-"),
            ]
            if not include_side:
                values = values[1:]
            for col, value in enumerate(values):
                table.setItem(idx, col, QTableWidgetItem(value))
            equipment_col = len(headers) - 2
            actions_col = len(headers) - 1
            if self.character_inspector.has_items(character):
                btn = QPushButton("Equipo")
                self._configure_button(btn)
                btn.clicked.connect(lambda _, c=character: self.open_character_items_inspector(c))
                table.setCellWidget(idx, equipment_col, btn)
            if self.character_inspector.has_actions(character):
                btn = QPushButton("Inspector IA")
                self._configure_button(btn)
                btn.clicked.connect(lambda _, c=character: self.open_character_actions_inspector(c))
                table.setCellWidget(idx, actions_col, btn)
        table.setAlternatingRowColors(True)
        self._configure_table(table)
        return table

    def _build_commands_table(self, commands: list[dict[str, Any]]) -> QTableWidget:
        table = QTableWidget(len(commands), 2)
        table.setHorizontalHeaderLabels(["Orden", "Comando"])
        for idx, command in enumerate(commands):
            order = command.get("command_order")
            table.setItem(idx, 0, QTableWidgetItem(str(order if order is not None else "-")))
            table.setItem(idx, 1, QTableWidgetItem(str(command.get("command_tag") or "-")))
        table.setAlternatingRowColors(True)
        self._configure_table(table)
        return table

    def _collect_attribute_keys(
        self,
        rows: list[dict[str, Any]],
        key_name: str,
        *,
        exclude_keys: set[str] | None = None,
        exclude_prefixes: set[str] | None = None,
    ) -> list[str]:
        keys: set[str] = set()
        exclude_keys = {str(key).lower() for key in (exclude_keys or set())}
        exclude_prefixes = {str(prefix).lower() for prefix in (exclude_prefixes or set())}
        for row in rows:
            attrs = row.get(key_name)
            if not isinstance(attrs, dict):
                continue
            for key in attrs.keys():
                key_text = str(key)
                if key_text.lower() in exclude_keys:
                    continue
                key_lower = key_text.lower()
                if any(key_lower.startswith(prefix) for prefix in exclude_prefixes):
                    continue
                keys.add(key_text)
        return sorted(keys)

    def _parse_room_actions(self, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        text = str(value).strip()
        if not text:
            return []
        separators = [",", ";", "|", " "]
        tokens = [text]
        for sep in separators:
            next_tokens: list[str] = []
            for token in tokens:
                next_tokens.extend(token.split(sep))
            tokens = next_tokens
        return [token.strip() for token in tokens if token.strip()]

    def _collect_room_actions(
        self, detail: dict[str, Any]
    ) -> list[tuple[str, str, Any, list[dict[str, str]]]]:
        rows: list[tuple[str, str, Any, list[dict[str, str]]]] = []
        rooms = detail.get("rooms") or []
        fallback_actions = self._room_actions_from_cleaned(detail)
        for room in rooms:
            side = str(room.get("side") or "-")
            room_id = str(room.get("room_id") or "-")
            room_design_id = room.get("room_design_id")
            attrs = room.get("room_attributes_json")
            if not isinstance(attrs, dict):
                continue
            actions = self._room_actions_for_room(room, attrs, fallback_actions)
            if actions:
                rows.append((side, room_id, room_design_id, actions))
        return rows

    def _has_room_actions(self, detail: dict[str, Any]) -> bool:
        rooms = detail.get("rooms") or []
        if not rooms:
            return False
        fallback_actions = self._room_actions_from_cleaned(detail)
        for room in rooms:
            attrs = room.get("room_attributes_json")
            if not isinstance(attrs, dict):
                attrs = {}
            if self._room_actions_for_room(room, attrs, fallback_actions):
                return True
        return False

    def open_room_actions_inspector(self, detail: dict[str, Any], room: dict[str, Any] | None = None) -> None:
        if room is None:
            rows = self._collect_room_actions(detail)
        else:
            attrs = room.get("room_attributes_json")
            if not isinstance(attrs, dict):
                attrs = {}
            actions = self._room_actions_for_room(room, attrs, self._room_actions_from_cleaned(detail))
            side = str(room.get("side") or "-")
            room_id = str(room.get("room_id") or "-")
            room_design_id = room.get("room_design_id")
            rows = [(side, room_id, room_design_id, actions)] if actions else []
        total_rows = sum(len(actions) for _, _, _, actions in rows)
        table = QTableWidget(total_rows or 1, 3)
        table.setHorizontalHeaderLabels(["ID", "RoomConditionID", "RoomActionID"])
        row_idx = 0
        for side, room_id, room_design_id, actions in rows:
            for idx, action in enumerate(actions, start=1):
                action_id = action.get("action_id") or "-"
                condition_id = action.get("condition_id") or "-"
                action_index = action.get("id") or str(idx)
                try:
                    action_index_int = int(str(action_index))
                    action_index = str(action_index_int + 1)
                except Exception:
                    action_index = str(action_index)
                action_label, condition_label = self.catalogo.resolve_action_condition(action_id, condition_id)
                action_label = self.room_item_mapping.resolve_action_label(
                    room_design_id,
                    action_id,
                    fallback_action_name=action_label,
                )
                table.setItem(row_idx, 0, QTableWidgetItem(str(action_index)))
                table.setItem(row_idx, 1, QTableWidgetItem(condition_label))
                table.setItem(row_idx, 2, QTableWidgetItem(action_label))
                row_idx += 1
        if total_rows == 0:
            table.setItem(0, 0, QTableWidgetItem("-"))
            table.setItem(0, 1, QTableWidgetItem("-"))
            table.setItem(0, 2, QTableWidgetItem("-"))
        table.setAlternatingRowColors(True)
        self._configure_table(table)

        wrapper = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        title = QLabel("Room Actions")
        title.setObjectName("panelTitle")
        layout.addWidget(title)
        layout.addWidget(table)
        wrapper.setLayout(layout)
        self._open_child("Inspector IA", wrapper)

    def open_character_actions_inspector(self, character: dict[str, Any]) -> None:
        actions = self.character_inspector.get_character_actions(character)
        table = QTableWidget(len(actions) or 1, 3)
        table.setHorizontalHeaderLabels(["ID", "Condicion", "Accion"])
        for row_idx, action in enumerate(actions):
            table.setItem(row_idx, 0, QTableWidgetItem(action.get("index", "-")))
            table.setItem(row_idx, 1, QTableWidgetItem(action.get("condition_label", "Sin traduccion")))
            table.setItem(row_idx, 2, QTableWidgetItem(action.get("action_label", "Sin traduccion")))
        if not actions:
            table.setItem(0, 0, QTableWidgetItem("-"))
            table.setItem(0, 1, QTableWidgetItem("-"))
            table.setItem(0, 2, QTableWidgetItem("-"))
        table.setAlternatingRowColors(True)
        self._configure_table(table)

        wrapper = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        title = QLabel("IA de Tripulante")
        title.setObjectName("panelTitle")
        layout.addWidget(title)
        layout.addWidget(table)
        wrapper.setLayout(layout)
        self._open_child("Inspector IA", wrapper)

    def open_character_items_inspector(self, character: dict[str, Any]) -> None:
        items = self.character_inspector.get_character_items(character)
        table = QTableWidget(len(items) or 1, 5)
        table.setHorizontalHeaderLabels(["ID", "Objeto", "Bonus", "Valor", "Cantidad"])
        for row_idx, item in enumerate(items):
            table.setItem(row_idx, 0, QTableWidgetItem(item.get("index", "-")))
            table.setItem(row_idx, 1, QTableWidgetItem(item.get("item_name", "Sin traduccion")))
            table.setItem(row_idx, 2, QTableWidgetItem(item.get("bonus_type", "-")))
            table.setItem(row_idx, 3, QTableWidgetItem(item.get("bonus_value", "-")))
            table.setItem(row_idx, 4, QTableWidgetItem(item.get("quantity", "-")))
        if not items:
            for col in range(5):
                table.setItem(0, col, QTableWidgetItem("-"))
        table.setAlternatingRowColors(True)
        self._configure_table(table)

        wrapper = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        title = QLabel("Equipo")
        title.setObjectName("panelTitle")
        layout.addWidget(title)
        layout.addWidget(table)
        wrapper.setLayout(layout)
        self._open_child("Equipo", wrapper)

    def _refresh_catalog_status(self) -> None:
        if self.catalog_status_label is None:
            return
        if self.catalog_base_dir:
            self.catalog_status_label.setText("Catalogos: local (ruta configurada)")
        else:
            self.catalog_status_label.setText("Catalogos: sin ruta local")

    def _on_catalog_status(self, status: str) -> None:
        if self.catalog_status_label is None:
            return
        messages = {
            "local": "Catalogos: local (OK)",
            "db": "Catalogos: fallback DB",
            "current_name": "Catalogos: usando nombre existente",
            "placeholder": "Catalogos: sin traduccion",
            "missing_path": "Catalogos: ruta no configurada",
            "missing_file": "Catalogos: archivo faltante",
            "parse_error": "Catalogos: error al leer archivos",
        }
        self.catalog_status_label.setText(messages.get(status, "Catalogos: estado desconocido"))

    def _configure_table(self, table: QTableWidget) -> None:
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        table.resizeColumnsToContents()
        table.resizeRowsToContents()

    def _configure_button(self, button: QPushButton) -> None:
        button.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        hint = button.sizeHint()
        if hint.isValid():
            button.setMinimumWidth(hint.width())

    def _apply_catalog_dir(self) -> None:
        value = self.catalog_path_input.text().strip()
        if not value:
            QMessageBox.warning(self, "Catalogos", "La ruta esta vacia.")
            self.catalog_base_dir = None
            self.catalogo.set_base_dir(None)
            self._refresh_catalog_status()
            return
        path = Path(value)
        if not path.exists():
            QMessageBox.warning(self, "Catalogos", "La ruta no existe.")
            self.catalog_base_dir = None
            self.catalogo.set_base_dir(None)
            self._refresh_catalog_status()
            return
        self.catalog_base_dir = path
        self.catalogo.set_base_dir(path)
        self._refresh_catalog_status()

    def _browse_catalog_dir(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta Data/Prod")
        if not selected:
            return
        self.catalog_path_input.setText(selected)
        self._apply_catalog_dir()

    def _auto_detect_catalog_dir(self) -> None:
        auto = CatalogoResolver.default_base_dir()
        if auto is None:
            QMessageBox.warning(self, "Catalogos", "No se encontro ruta por defecto.")
            self.catalog_base_dir = None
            self.catalogo.set_base_dir(None)
            self._refresh_catalog_status()
            return
        self.catalog_path_input.setText(str(auto))
        self._apply_catalog_dir()

    def _room_actions_for_room(
        self,
        room: dict[str, Any],
        attrs: dict[str, Any],
        fallback_actions: dict[str, list[dict[str, str]]],
    ) -> list[dict[str, str]]:
        normalized = attrs.get("RoomActionsNormalized")
        if isinstance(normalized, list) and normalized:
            out: list[dict[str, str]] = []
            for entry in normalized:
                if not isinstance(entry, dict):
                    continue
                out.append(
                    {
                        "id": str(entry.get("index") or "-"),
                        "condition_id": str(entry.get("condition_type_id") or "-"),
                        "action_id": str(entry.get("action_type_id") or entry.get("room_action_id") or "-"),
                    }
                )
            if out:
                return out
        raw_value = attrs.get("RoomAction")
        if raw_value is None:
            raw_value = attrs.get("RoomActions")
        actions = self._parse_room_actions(raw_value)
        if actions:
            return [{"id": str(idx), "condition_id": "-", "action_id": value} for idx, value in enumerate(actions, start=1)]
        room_id = str(room.get("room_id") or "")
        if room_id and room_id in fallback_actions:
            return fallback_actions[room_id]
        return []

    def _room_actions_from_cleaned(self, detail: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
        api_flow = detail.get("api_flow_event") or {}
        cleaned = api_flow.get("response_body_cleaned")
        if not cleaned:
            return {}
        try:
            payload = json.loads(cleaned)
        except Exception:
            return {}
        room_actions: dict[str, list[dict[str, str]]] = {}
        for node in self._iter_nodes(payload):
            if node.get("tag") != "Room":
                continue
            attrs = node.get("attributes")
            if not isinstance(attrs, dict):
                continue
            room_id = attrs.get("RoomId")
            if room_id is None:
                continue
            actions = []
            for action_node in self._extract_children_by_path(node, ["RoomActions", "RoomAction"]):
                action_attrs = action_node.get("attributes")
                if not isinstance(action_attrs, dict):
                    continue
                actions.append(
                    {
                        "id": str(action_attrs.get("RoomActionIndex") or len(actions) + 1),
                        "condition_id": str(action_attrs.get("ConditionTypeId") or "-"),
                        "action_id": str(action_attrs.get("ActionTypeId") or action_attrs.get("RoomActionId") or "-"),
                    }
                )
            if actions:
                room_actions[str(room_id)] = actions
        return room_actions

    def _extract_children_by_path(
        self, node: dict[str, Any], path: list[str | None]
    ) -> list[dict[str, Any]]:
        current: list[dict[str, Any]] = [node]
        for expected_tag in path:
            next_nodes: list[dict[str, Any]] = []
            for item in current:
                children = item.get("children")
                if not isinstance(children, list):
                    continue
                for child in children:
                    if not isinstance(child, dict):
                        continue
                    if expected_tag is None or child.get("tag") == expected_tag:
                        next_nodes.append(child)
            current = next_nodes
            if not current:
                break
        return current

    def _iter_nodes(self, node: dict[str, Any]) -> list[dict[str, Any]]:
        stack = [node]
        out: list[dict[str, Any]] = []
        while stack:
            current = stack.pop()
            if not isinstance(current, dict):
                continue
            out.append(current)
            children = current.get("children")
            if isinstance(children, list):
                for child in children:
                    if isinstance(child, dict):
                        stack.append(child)
            attrs = current.get("attributes")
            if isinstance(attrs, dict):
                for value in attrs.values():
                    if isinstance(value, dict):
                        stack.append(value)
                    elif isinstance(value, list):
                        for entry in value:
                            if isinstance(entry, dict):
                                stack.append(entry)
        return out
