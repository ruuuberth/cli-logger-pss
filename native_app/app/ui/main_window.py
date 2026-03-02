from __future__ import annotations

import json
from datetime import datetime

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
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.config import settings
from app.services.api_flow_capture import ApiFlowCaptureManager
from app.services.api_flow_storage import ApiFlowFilters, ApiFlowRepository


class ApiFlowBridge(QObject):
    event_received = Signal(dict)
    status_changed = Signal(str)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.api_flow_repository = ApiFlowRepository()
        self.api_flow_capture_manager = ApiFlowCaptureManager()
        self.api_flow_bridge = ApiFlowBridge(self)
        self.api_flow_bridge.event_received.connect(self._on_api_flow_event)
        self.api_flow_bridge.status_changed.connect(self._on_api_flow_status)
        self.api_flow_capture_manager.subscribe(
            lambda event: self.api_flow_bridge.event_received.emit(event)
        )
        self.api_flow_capture_manager.subscribe_status(
            lambda message: self.api_flow_bridge.status_changed.emit(message)
        )

        self.api_flow_pending_events: list[dict] = []
        self.api_flow_total_live_events = 0
        self.api_flow_page = 0
        self.api_flow_page_size = 200
        self.api_flow_current_rows: list[dict] = []

        self.api_flow_flush_timer = QTimer(self)
        self.api_flow_flush_timer.setInterval(1000)
        self.api_flow_flush_timer.timeout.connect(self._flush_api_flow_events)

        self.setWindowTitle("PixelStarships Battle Logger Native")
        self.resize(1200, 760)
        self.setCentralWidget(self._build_api_flow_tab())

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
        self.api_flow_search_input.setPlaceholderText("Buscar host/path...")
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

        self.api_flow_table = QTableWidget(0, 7)
        self.api_flow_table.setHorizontalHeaderLabels(
            ["Hora", "Metodo", "Endpoint", "Status", "Latencia(ms)", "Tamano", "Host"]
        )
        self.api_flow_table.horizontalHeader().setStretchLastSection(True)
        self.api_flow_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.api_flow_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.api_flow_table.itemSelectionChanged.connect(self._on_api_flow_row_selected)

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
        self.api_flow_detail = QPlainTextEdit()
        self.api_flow_detail.setReadOnly(True)
        self.api_flow_detail.setPlaceholderText("Selecciona un evento para ver detalles...")

        content.addLayout(controls)
        content.addLayout(filters)
        content.addLayout(pagination)
        content.addWidget(self.api_flow_status_label)
        content.addWidget(self.api_flow_counter_label)
        content.addWidget(self.api_flow_session_label)
        content.addWidget(self.api_flow_count_label)
        content.addWidget(self.api_flow_table)
        content.addWidget(self.api_flow_detail)
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
        self.api_flow_total_live_events += 1
        self.api_flow_counter_label.setText(f"Eventos (sesion): {self.api_flow_total_live_events}")

    @Slot(str)
    def _on_api_flow_status(self, message: str) -> None:
        self.api_flow_status_label.setText(f"Estado: {message}")
        if not self.api_flow_capture_manager.is_running():
            self.api_flow_start_button.setEnabled(True)
            self.api_flow_stop_button.setEnabled(False)

    @Slot()
    def _flush_api_flow_events(self) -> None:
        if self.api_flow_pending_events:
            pending = list(self.api_flow_pending_events)
            self.api_flow_pending_events.clear()
            self.api_flow_repository.save_events(pending)
            self.api_flow_repository.purge(
                retention_days=settings.API_FLOW_RETENTION_DAYS,
                max_db_mb=settings.API_FLOW_MAX_DB_MB,
            )
        if self.api_flow_auto_scroll_checkbox.isChecked():
            self.api_flow_page = 0
            self.reload_api_flow_page()

    def _current_api_flow_filters(self) -> ApiFlowFilters:
        status_min = self.api_flow_status_min.value() or None
        status_max = self.api_flow_status_max.value() or None
        if status_min is not None and status_max is not None and status_max < status_min:
            status_max = status_min

        method = self.api_flow_method_combo.currentText()
        if method == "Todos":
            method = ""

        return ApiFlowFilters(
            search=self.api_flow_search_input.text().strip(),
            method=method,
            status_min=status_min,
            status_max=status_max,
            only_errors=self.api_flow_only_errors.isChecked(),
            time_from=self._parse_iso_datetime(self.api_flow_time_from.text().strip()),
            time_to=self._parse_iso_datetime(self.api_flow_time_to.text().strip()),
        )

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
        payload = self.api_flow_repository.list_events(
            filters=self._current_api_flow_filters(),
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
            method = str(row.get("method") or "-")
            path = str(row.get("path") or row.get("url_full") or "-")
            status = str(row.get("status_code") or "-")
            latency = str(row.get("duration_ms") or "-")
            size = row.get("response_size_bytes") or row.get("request_size_bytes") or 0
            host = str(row.get("host") or "-")
            self.api_flow_table.setItem(idx, 0, QTableWidgetItem(captured_at[:19].replace("T", " ")))
            self.api_flow_table.setItem(idx, 1, QTableWidgetItem(method))
            self.api_flow_table.setItem(idx, 2, QTableWidgetItem(path))
            self.api_flow_table.setItem(idx, 3, QTableWidgetItem(status))
            self.api_flow_table.setItem(idx, 4, QTableWidgetItem(latency))
            self.api_flow_table.setItem(idx, 5, QTableWidgetItem(str(size)))
            self.api_flow_table.setItem(idx, 6, QTableWidgetItem(host))

        if total == 0:
            self.api_flow_page_label.setText("Pagina: 0")
            self.api_flow_prev_page_button.setEnabled(False)
            self.api_flow_next_page_button.setEnabled(False)
            self.api_flow_detail.setPlainText("")
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
        self.api_flow_page = 0
        self.api_flow_total_live_events = 0
        self.api_flow_counter_label.setText("Eventos (sesion): 0")
        self.reload_api_flow_page()

    def _on_api_flow_row_selected(self) -> None:
        selected = self.api_flow_table.selectedItems()
        if not selected:
            return
        row_index = selected[0].row()
        if row_index < 0 or row_index >= len(self.api_flow_current_rows):
            return
        row = self.api_flow_current_rows[row_index]
        detail = {
            "captured_at": row.get("captured_at"),
            "session_id": row.get("session_id"),
            "method": row.get("method"),
            "url_full": row.get("url_full"),
            "status_code": row.get("status_code"),
            "duration_ms": row.get("duration_ms"),
            "tls": row.get("tls"),
            "request_size_bytes": row.get("request_size_bytes"),
            "response_size_bytes": row.get("response_size_bytes"),
            "error_text": row.get("error_text"),
            "request_headers": row.get("request_headers_json"),
            "response_headers": row.get("response_headers_json"),
            "request_body_preview": row.get("request_body_preview"),
            "response_body_preview": row.get("response_body_preview"),
        }
        self.api_flow_detail.setPlainText(json.dumps(detail, indent=2, ensure_ascii=False))

    def closeEvent(self, event: QCloseEvent) -> None:
        self.api_flow_flush_timer.stop()
        self.api_flow_capture_manager.stop_capture()
        super().closeEvent(event)
