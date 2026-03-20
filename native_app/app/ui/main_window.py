from __future__ import annotations
from functools import partial
from datetime import datetime
from threading import Thread

from PySide6.QtCore import QObject, QTimer, Signal, Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.config import settings
from app.services.api_flow_capture import ApiFlowCaptureManager
from app.services.api_flow_storage import ApiFlowRepository
from app.ui.battle_inspector_window import BattleInspectorWindow


class ApiFlowBridge(QObject):
    event_received = Signal(dict)
    status_changed = Signal(str)
    startup_sync_finished = Signal(dict)


class MainWindow(QMainWindow):
    API_FLOW_PENDING_MAX_EVENTS = 10_000

    def __init__(self):
        super().__init__()
        self.api_flow_repository = ApiFlowRepository()
        self.api_flow_capture_manager = ApiFlowCaptureManager()
        self.api_flow_bridge = ApiFlowBridge(self)
        self.api_flow_bridge.event_received.connect(self._on_api_flow_event)
        self.api_flow_bridge.status_changed.connect(self._on_api_flow_status)
        self.api_flow_bridge.startup_sync_finished.connect(self._on_startup_sync_finished)
        self.api_flow_capture_manager.subscribe(
            lambda event: self.api_flow_bridge.event_received.emit(event)
        )
        self.api_flow_capture_manager.subscribe_status(
            lambda message: self.api_flow_bridge.status_changed.emit(message)
        )

        self.api_flow_pending_events: list[dict] = []
        self.api_flow_total_live_events = 0
        self.api_flow_dropped_pending_events = 0
        self.api_flow_flush_failures = 0
        self.api_flow_last_capture_status = "detenido"
        self.api_flow_page = 0
        self.api_flow_page_size = 200
        self.api_flow_current_rows: list[dict] = []
        self.battle_inspector_windows: list[BattleInspectorWindow] = []
        self.startup_sync_running = False
        self.startup_sync_thread: Thread | None = None

        self.api_flow_flush_timer = QTimer(self)
        self.api_flow_flush_timer.setInterval(1000)
        self.api_flow_flush_timer.timeout.connect(self._flush_api_flow_events)

        self.setWindowTitle("PixelStarships Battle Logger Native")
        self.resize(1200, 760)
        self.setCentralWidget(self._build_api_flow_tab())
        QTimer.singleShot(0, self._start_startup_sync)

    def _build_api_flow_tab(self) -> QWidget:
        tab = QWidget()
        content = QVBoxLayout()

        self.api_flow_status_label = QLabel("Estado: detenido")
        self.api_flow_counter_label = QLabel("Eventos: 0")
        self.api_flow_session_label = QLabel("Sesion: -")

        self.api_flow_start_button = QPushButton("Iniciar captura")
        self.api_flow_start_button.clicked.connect(self.start_api_flow_capture)
        self.api_flow_stop_button = QPushButton("Detener")
        self.api_flow_stop_button.clicked.connect(self.stop_api_flow_capture)
        self.api_flow_stop_button.setEnabled(False)
        self.api_flow_refresh_button = QPushButton("Refrescar")
        self.api_flow_refresh_button.clicked.connect(self.reload_api_flow_page)
        self.api_flow_clear_button = QPushButton("Limpiar historial")
        self.api_flow_clear_button.clicked.connect(self.clear_api_flow_history)
        self.api_flow_auto_scroll_checkbox = QCheckBox("Auto-scroll")
        self.api_flow_auto_scroll_checkbox.setChecked(True)

        controls = QHBoxLayout()
        controls.addWidget(self.api_flow_start_button)
        controls.addWidget(self.api_flow_stop_button)
        controls.addWidget(self.api_flow_refresh_button)
        controls.addWidget(self.api_flow_clear_button)
        controls.addWidget(self.api_flow_auto_scroll_checkbox)
        controls.addStretch()

        self.api_flow_search_input = QLineEdit()
        self.api_flow_search_input.setPlaceholderText("Buscar atacante/defensor/battle id...")
        self.api_flow_search_input.textChanged.connect(self.apply_api_flow_filters)
        self.api_flow_method_combo = QComboBox()
        self.api_flow_method_combo.addItems(["Todos", "GET", "POST", "PUT", "PATCH", "DELETE"])
        self.api_flow_method_combo.currentTextChanged.connect(self.apply_api_flow_filters)
        self.api_flow_status_min = QSpinBox()
        self.api_flow_status_min.setRange(0, 999)
        self.api_flow_status_min.setPrefix("Min ")
        self.api_flow_status_min.valueChanged.connect(self.apply_api_flow_filters)
        self.api_flow_status_max = QSpinBox()
        self.api_flow_status_max.setRange(0, 999)
        self.api_flow_status_max.setPrefix("Max ")
        self.api_flow_status_max.valueChanged.connect(self.apply_api_flow_filters)
        self.api_flow_only_errors = QCheckBox("Solo errores")
        self.api_flow_only_errors.stateChanged.connect(self.apply_api_flow_filters)
        self.api_flow_time_from = QLineEdit()
        self.api_flow_time_from.setPlaceholderText("Desde ISO (YYYY-MM-DDTHH:MM:SS)")
        self.api_flow_time_from.editingFinished.connect(self.apply_api_flow_filters)
        self.api_flow_time_to = QLineEdit()
        self.api_flow_time_to.setPlaceholderText("Hasta ISO (YYYY-MM-DDTHH:MM:SS)")
        self.api_flow_time_to.editingFinished.connect(self.apply_api_flow_filters)
        self.api_flow_reset_filters_button = QPushButton("Limpiar filtros")
        self.api_flow_reset_filters_button.clicked.connect(self.reset_api_flow_filters)

        filters = QHBoxLayout()
        filters.addWidget(self.api_flow_search_input)
        filters.addWidget(QLabel("Metodo"))
        filters.addWidget(self.api_flow_method_combo)
        filters.addWidget(self.api_flow_status_min)
        filters.addWidget(self.api_flow_status_max)
        filters.addWidget(self.api_flow_only_errors)
        filters.addWidget(self.api_flow_time_from)
        filters.addWidget(self.api_flow_time_to)
        filters.addWidget(self.api_flow_reset_filters_button)

        self.api_flow_table = QTableWidget(0, 8)
        self.api_flow_table.setHorizontalHeaderLabels(
            ["Hora", "Atacante", "Defensor", "Resultado", "Botin", "Copas", "BattleId", "Inspector"]
        )
        self.api_flow_table.horizontalHeader().setStretchLastSection(True)
        self.api_flow_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.api_flow_table.setSelectionMode(QAbstractItemView.SingleSelection)

        self.api_flow_prev_page_button = QPushButton("Anterior")
        self.api_flow_prev_page_button.clicked.connect(self.api_flow_prev_page)
        self.api_flow_next_page_button = QPushButton("Siguiente")
        self.api_flow_next_page_button.clicked.connect(self.api_flow_next_page)
        self.api_flow_page_label = QLabel("Pagina: 1")

        pagination = QHBoxLayout()
        pagination.addWidget(self.api_flow_prev_page_button)
        pagination.addWidget(self.api_flow_next_page_button)
        pagination.addWidget(self.api_flow_page_label)
        pagination.addStretch()

        self.api_flow_count_label = QLabel("Registros: 0")

        content.addLayout(controls)
        content.addLayout(filters)
        content.addLayout(pagination)
        content.addWidget(self.api_flow_status_label)
        content.addWidget(self.api_flow_counter_label)
        content.addWidget(self.api_flow_session_label)
        content.addWidget(self.api_flow_count_label)
        content.addWidget(self.api_flow_table)
        tab.setLayout(content)

        self.reload_api_flow_page()
        return tab

    def start_api_flow_capture(self) -> None:
        try:
            session = self.api_flow_capture_manager.start_capture()
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"No se pudo iniciar captura: {exc}")
            return

        self.api_flow_session_label.setText(f"Sesion: {session.session_id}")
        self.api_flow_status_label.setText(
            f"Estado: activo en {session.listen_host}:{session.listen_port}"
        )
        self.api_flow_start_button.setEnabled(False)
        self.api_flow_stop_button.setEnabled(True)
        if not self.api_flow_flush_timer.isActive():
            self.api_flow_flush_timer.start()

    def stop_api_flow_capture(self) -> None:
        self.api_flow_capture_manager.stop_capture()
        self.api_flow_start_button.setEnabled(True)
        self.api_flow_stop_button.setEnabled(False)
        self.api_flow_flush_timer.stop()
        self._flush_api_flow_events()

    @Slot(dict)
    def _on_api_flow_event(self, payload: dict) -> None:
        self.api_flow_pending_events.append(payload)
        dropped = self._enforce_pending_limit()
        if dropped:
            self.api_flow_dropped_pending_events += dropped
            self.api_flow_status_label.setText(
                f"Estado: backlog limitado, descartados {self.api_flow_dropped_pending_events} eventos"
            )
        self.api_flow_total_live_events += 1
        self.api_flow_counter_label.setText(f"Eventos (sesion): {self.api_flow_total_live_events}")

    @Slot(str)
    def _on_api_flow_status(self, message: str) -> None:
        self.api_flow_last_capture_status = message
        self.api_flow_status_label.setText(f"Estado: {message}")
        if not self.api_flow_capture_manager.is_running():
            self.api_flow_start_button.setEnabled(True)
            self.api_flow_stop_button.setEnabled(False)

    @Slot()
    def _flush_api_flow_events(self) -> None:
        self._flush_pending_events()
        if self.api_flow_auto_scroll_checkbox.isChecked():
            self.api_flow_page = 0
            self.reload_api_flow_page()

    def _flush_pending_events(self) -> None:
        if not self.api_flow_pending_events:
            return

        pending = list(self.api_flow_pending_events)
        self.api_flow_pending_events.clear()
        saved_count = self.api_flow_repository.save_events(pending)
        if saved_count < len(pending):
            self.api_flow_flush_failures += 1
            unsaved = pending[max(0, saved_count) :]
            self.api_flow_pending_events = unsaved + self.api_flow_pending_events
            dropped = self._enforce_pending_limit()
            if dropped:
                self.api_flow_dropped_pending_events += dropped
            self.api_flow_status_label.setText(
                "Estado: error de persistencia, reintentos="
                f"{self.api_flow_flush_failures}, pendientes={len(self.api_flow_pending_events)}"
            )
            return

        if self.api_flow_flush_failures:
            self.api_flow_flush_failures = 0
            self.api_flow_status_label.setText(f"Estado: {self.api_flow_last_capture_status}")

        self.api_flow_repository.purge(
            retention_days=settings.API_FLOW_RETENTION_DAYS,
            max_db_mb=settings.API_FLOW_MAX_DB_MB,
        )

    def _start_startup_sync(self) -> None:
        if self.startup_sync_running:
            return
        self.startup_sync_running = True
        self.api_flow_status_label.setText("Estado: inicializando historial de batallas...")
        thread = Thread(target=self._run_startup_sync_worker, daemon=True, name="startup-sync")
        self.startup_sync_thread = thread
        thread.start()

    def _run_startup_sync_worker(self) -> None:
        repo = ApiFlowRepository()
        result = {"ok": True}
        try:
            while repo.backfill_response_body_cleaned(batch_size=100) > 0:
                pass
            while repo.sync_battle_replays_from_api_flow(batch_size=500) > 0:
                pass
            while repo.sync_battle_replay_children(batch_size=200) > 0:
                pass
            while repo.backfill_room_attributes(batch_size=200) > 0:
                pass
        except Exception as exc:
            result = {"ok": False, "error": str(exc)}
        self.api_flow_bridge.startup_sync_finished.emit(result)

    @Slot(dict)
    def _on_startup_sync_finished(self, payload: dict) -> None:
        self.startup_sync_running = False
        if not payload.get("ok", True):
            self.api_flow_status_label.setText(
                f"Estado: error en inicializacion ({payload.get('error', 'desconocido')})"
            )
            return

        if not self.api_flow_capture_manager.is_running():
            self.api_flow_status_label.setText(f"Estado: {self.api_flow_last_capture_status}")
        self.reload_api_flow_page()

    def _enforce_pending_limit(self) -> int:
        if len(self.api_flow_pending_events) <= self.API_FLOW_PENDING_MAX_EVENTS:
            return 0
        dropped = len(self.api_flow_pending_events) - self.API_FLOW_PENDING_MAX_EVENTS
        del self.api_flow_pending_events[:dropped]
        return dropped

    def _parse_iso_datetime(self, value: str) -> datetime | None:
        if not value:
            return None
        try:
            normalized = value
            if normalized.endswith("Z"):
                normalized = normalized[:-1] + "+00:00"
            return datetime.fromisoformat(normalized)
        except ValueError:
            return None

    def reload_api_flow_page(self) -> None:
        payload = self.api_flow_repository.list_battle_replays(
            search=self.api_flow_search_input.text().strip(),
            page=self.api_flow_page,
            page_size=self.api_flow_page_size,
        )
        total = payload["total"]
        rows = payload["rows"]
        self.api_flow_current_rows = rows
        self.api_flow_count_label.setText(f"Registros: {total}")

        self.api_flow_table.setRowCount(len(rows))
        for idx, row in enumerate(rows):
            captured_at = str(row.get("captured_at") or "")
            attacker = str(row.get("attacker_name") or "-")
            defender = str(row.get("defender_name") or "-")
            outcome = str(row.get("outcome_type") or "-")
            botin = (
                f"M {row.get('win_minerals_result') or 0}/{row.get('lose_minerals_result') or 0}"
                f" | G {row.get('win_gas_result') or 0}/{row.get('lose_gas_result') or 0}"
            )
            copas = f"{row.get('win_trophy_result') or 0}/{row.get('lose_trophy_result') or 0}"
            battle_id = str(row.get("battle_id") or "-")
            self.api_flow_table.setItem(idx, 0, QTableWidgetItem(captured_at[:19].replace("T", " ")))
            self.api_flow_table.setItem(idx, 1, QTableWidgetItem(attacker))
            self.api_flow_table.setItem(idx, 2, QTableWidgetItem(defender))
            self.api_flow_table.setItem(idx, 3, QTableWidgetItem(outcome))
            self.api_flow_table.setItem(idx, 4, QTableWidgetItem(botin))
            self.api_flow_table.setItem(idx, 5, QTableWidgetItem(copas))
            self.api_flow_table.setItem(idx, 6, QTableWidgetItem(battle_id))
            inspect_button = QPushButton("Inspeccionar")
            inspect_button.clicked.connect(partial(self.open_battle_inspector, row.get("id")))
            self.api_flow_table.setCellWidget(idx, 7, inspect_button)

        if total == 0:
            self.api_flow_page_label.setText("Pagina: 0")
            self.api_flow_prev_page_button.setEnabled(False)
            self.api_flow_next_page_button.setEnabled(False)
            return

        max_page = (total - 1) // self.api_flow_page_size
        if self.api_flow_page > max_page:
            self.api_flow_page = max_page
            self.reload_api_flow_page()
            return
        self.api_flow_page_label.setText(f"Pagina: {self.api_flow_page + 1}")
        self.api_flow_prev_page_button.setEnabled(self.api_flow_page > 0)
        self.api_flow_next_page_button.setEnabled(self.api_flow_page < max_page)

    def apply_api_flow_filters(self, *_) -> None:
        self.api_flow_page = 0
        self.reload_api_flow_page()

    def reset_api_flow_filters(self) -> None:
        self.api_flow_search_input.setText("")
        self.api_flow_method_combo.setCurrentText("Todos")
        self.api_flow_status_min.setValue(0)
        self.api_flow_status_max.setValue(0)
        self.api_flow_only_errors.setChecked(False)
        self.api_flow_time_from.setText("")
        self.api_flow_time_to.setText("")
        self.reload_api_flow_page()

    def api_flow_next_page(self) -> None:
        self.api_flow_page += 1
        self.reload_api_flow_page()

    def api_flow_prev_page(self) -> None:
        if self.api_flow_page == 0:
            return
        self.api_flow_page -= 1
        self.reload_api_flow_page()

    def clear_api_flow_history(self) -> None:
        answer = QMessageBox.question(
            self,
            "Confirmar",
            "¿Seguro que deseas eliminar el historial de Flujo de la API?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.api_flow_repository.clear_events()
        self.api_flow_repository.clear_battle_replays()
        self.api_flow_page = 0
        self.api_flow_total_live_events = 0
        self.api_flow_counter_label.setText("Eventos (sesion): 0")
        self.reload_api_flow_page()

    def open_battle_inspector(self, battle_replay_id: int | None) -> None:
        if battle_replay_id is None:
            return
        detail = self.api_flow_repository.get_battle_replay_detail(int(battle_replay_id))
        if detail is None:
            QMessageBox.warning(self, "Inspector", "No se encontro la batalla seleccionada.")
            return
        inspector = BattleInspectorWindow(detail, self)
        self.battle_inspector_windows.append(inspector)
        inspector.destroyed.connect(partial(self._on_battle_inspector_destroyed, inspector))
        inspector.show()

    def _on_battle_inspector_destroyed(self, inspector: BattleInspectorWindow, *_) -> None:
        if inspector in self.battle_inspector_windows:
            self.battle_inspector_windows.remove(inspector)

    def closeEvent(self, event: QCloseEvent) -> None:
        self.api_flow_flush_timer.stop()
        self._flush_pending_events()
        self.api_flow_capture_manager.stop_capture()
        super().closeEvent(event)
