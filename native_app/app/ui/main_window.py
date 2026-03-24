from __future__ import annotations
from functools import partial

from PySide6.QtCore import QTimer, Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from app.services.api_flow_list_service import ApiFlowListService, ApiFlowRowView
from app.services.perf_metrics import measure_perf
from app.services.api_flow_runtime import ApiFlowRuntime, ApiFlowRuntimeState
from app.services.process_resource_monitor import ProcessResourceMonitor
from app.ui.battle_inspector_window import BattleInspectorWindow
from app.ui.delegates.row_action_delegate import RowActionDelegate
from app.ui.models.api_flow_table_model import ApiFlowTableModel
from app.ui.api_flow_runtime_bridge import ApiFlowRuntimeBridge
from app.ui.ui_theme import window_font_qss
import logging


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.api_flow_runtime = ApiFlowRuntime()
        self.api_flow_list_service = ApiFlowListService(self.api_flow_runtime.repository)
        self.resource_monitor = ProcessResourceMonitor()
        self.api_flow_bridge = ApiFlowRuntimeBridge(self)
        self.api_flow_runtime.subscribe_state(
            lambda state: self.api_flow_bridge.state_changed.emit(ApiFlowRuntime.state_to_payload(state))
        )
        self.api_flow_runtime.subscribe_startup_sync_finished(
            lambda payload: self.api_flow_bridge.startup_sync_finished.emit(payload)
        )
        self.api_flow_runtime.subscribe_stop_flush_finished(
            lambda payload: self.api_flow_bridge.stop_flush_finished.emit(payload)
        )
        self.api_flow_runtime.subscribe_events_flushed(
            lambda payload: self.api_flow_bridge.events_flushed.emit(payload)
        )
        self.api_flow_bridge.state_changed.connect(self._on_runtime_state_changed)
        self.api_flow_bridge.startup_sync_finished.connect(self._on_startup_sync_finished)
        self.api_flow_bridge.stop_flush_finished.connect(self._on_stop_flush_finished)
        self.api_flow_bridge.events_flushed.connect(self._on_events_flushed)

        self.api_flow_page = 0
        self.api_flow_page_size = 200
        self.battle_inspector_windows: list[BattleInspectorWindow] = []

        self.api_flow_flush_timer = QTimer(self)
        self.api_flow_flush_timer.setInterval(1000)
        self.api_flow_flush_timer.timeout.connect(self._flush_api_flow_events)
        self.resource_monitor_timer = QTimer(self)
        self.resource_monitor_timer.setInterval(5000)
        self.resource_monitor_timer.timeout.connect(self._refresh_resource_labels)

        self.setWindowTitle("PixelStarships Battle Logger Native")
        self.resize(1200, 760)
        self.setStyleSheet(window_font_qss())
        self.setCentralWidget(self._build_api_flow_tab())
        QTimer.singleShot(0, self.start_api_flow_capture)
        QTimer.singleShot(0, self._start_startup_sync)
        self.resource_monitor_timer.start()

    def _build_api_flow_tab(self) -> QWidget:
        tab = QWidget()
        content = QVBoxLayout()

        self.api_flow_status_label = QLabel("Estado: detenido")
        self.api_flow_sync_label = QLabel("Historial: listo")
        self.api_flow_counter_label = QLabel("Eventos: 0")
        self.api_flow_session_label = QLabel("Sesion: -")

        self.api_flow_capture_button = QPushButton("Iniciar captura")
        self.api_flow_capture_button.clicked.connect(self.toggle_api_flow_capture)
        self.api_flow_refresh_button = QPushButton("Refrescar")
        self.api_flow_refresh_button.clicked.connect(self.reload_api_flow_page)
        self.api_flow_clear_button = QPushButton("Limpiar historial")
        self.api_flow_clear_button.clicked.connect(self.clear_api_flow_history)

        controls = QHBoxLayout()
        controls.addWidget(self.api_flow_capture_button)
        controls.addWidget(self.api_flow_refresh_button)
        controls.addWidget(self.api_flow_clear_button)
        controls.addStretch()

        self.api_flow_search_input = QLineEdit()
        self.api_flow_search_input.setPlaceholderText("Buscar atacante/defensor/battle id...")
        self.api_flow_search_input.textChanged.connect(self.apply_api_flow_filters)

        filters = QHBoxLayout()
        filters.addWidget(self.api_flow_search_input)
        filters.addStretch()

        self.api_flow_table_model = ApiFlowTableModel()
        self.api_flow_table = QTableView()
        self.api_flow_table.setModel(self.api_flow_table_model)
        self.api_flow_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.api_flow_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.api_flow_table.setAlternatingRowColors(True)
        self.api_flow_table.setSortingEnabled(False)
        self.api_flow_table.setWordWrap(False)
        self.api_flow_table.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.api_flow_table.verticalHeader().setDefaultSectionSize(34)
        self.api_flow_table.horizontalHeader().setStretchLastSection(False)
        self.api_flow_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.api_flow_table.horizontalHeader().setSectionResizeMode(8, QHeaderView.Fixed)
        self.api_flow_table.horizontalHeader().setSectionResizeMode(9, QHeaderView.Fixed)
        self.api_flow_table.setColumnWidth(8, 110)
        self.api_flow_table.setColumnWidth(9, 90)
        self.api_flow_table_action_delegate = RowActionDelegate(
            self.api_flow_table,
            action_map={8: "inspect", 9: "delete"},
        )
        self.api_flow_table_action_delegate.inspect_requested.connect(self._on_inspect_requested)
        self.api_flow_table_action_delegate.delete_requested.connect(self._on_delete_requested)
        self.api_flow_table.setItemDelegateForColumn(8, self.api_flow_table_action_delegate)
        self.api_flow_table.setItemDelegateForColumn(9, self.api_flow_table_action_delegate)
        self._configure_table(self.api_flow_table, resize_contents=True)

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
        self.app_resource_label = QLabel("App: CPU -, RAM -")
        self.proxy_resource_label = QLabel("Proxy: CPU -, RAM -")

        content.addLayout(controls)
        content.addLayout(filters)
        content.addLayout(pagination)
        content.addWidget(self.api_flow_status_label)
        content.addWidget(self.api_flow_sync_label)
        content.addWidget(self.api_flow_counter_label)
        content.addWidget(self.api_flow_session_label)
        content.addWidget(self.api_flow_count_label)
        content.addWidget(self.app_resource_label)
        content.addWidget(self.proxy_resource_label)
        content.addWidget(self.api_flow_table)
        tab.setLayout(content)

        self._refresh_resource_labels()
        self.reload_api_flow_page()
        return tab

    def start_api_flow_capture(self) -> None:
        try:
            self.api_flow_runtime.start_capture()
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"No se pudo iniciar captura: {exc}")
            return
        if not self.api_flow_flush_timer.isActive():
            self.api_flow_flush_timer.start()

    def stop_api_flow_capture(self) -> None:
        self.api_flow_runtime.stop_capture()
        self.api_flow_flush_timer.stop()

    def toggle_api_flow_capture(self) -> None:
        self.api_flow_runtime.toggle_capture()
        if self.api_flow_runtime.is_capture_running() and not self.api_flow_flush_timer.isActive():
            self.api_flow_flush_timer.start()

    @Slot()
    def _flush_api_flow_events(self) -> None:
        self.api_flow_runtime.flush_pending()

    def _start_startup_sync(self) -> None:
        self.api_flow_runtime.start_startup_sync()

    @Slot(dict)
    def _on_startup_sync_finished(self, payload: dict) -> None:
        if not payload.get("ok", True):
            self.api_flow_sync_label.setText(
                f"Historial: error ({payload.get('error', 'desconocido')})"
            )
            return

        self.api_flow_sync_label.setText("Historial: listo")
        self.reload_api_flow_page()

    @Slot(dict)
    def _on_stop_flush_finished(self, payload: dict) -> None:
        self.api_flow_status_label.setText(str(payload.get("message") or "Estado: detenido"))
        self.reload_api_flow_page()

    @Slot(dict)
    def _on_events_flushed(self, _payload: dict) -> None:
        return

    def reload_api_flow_page(self) -> None:
        with measure_perf("reload_api_flow_page", self.logger):
            payload = self.api_flow_list_service.list_page(
                search=self.api_flow_search_input.text().strip(),
                page=self.api_flow_page,
                page_size=self.api_flow_page_size,
            )
        total = payload.total
        rows = payload.rows
        self.api_flow_count_label.setText(f"Registros: {total}")
        self.api_flow_table_model.set_rows(rows)
        self._configure_table(self.api_flow_table, resize_contents=False)

        if total == 0:
            self.api_flow_page_label.setText("Pagina: 0")
            self.api_flow_prev_page_button.setEnabled(False)
            self.api_flow_next_page_button.setEnabled(False)
            return

        max_page = payload.max_page
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
        self.api_flow_list_service.clear_history()
        self.api_flow_page = 0
        self.reload_api_flow_page()

    def delete_api_flow_event(self, event_id: int | None, battle_id: str | None) -> None:
        if event_id is None:
            QMessageBox.warning(self, "Eliminar evento", "No se pudo identificar el evento.")
            return
        label = battle_id or "-"
        answer = QMessageBox.question(
            self,
            "Confirmar",
            f"¿Eliminar el evento de la batalla {label}?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        deleted = self.api_flow_list_service.delete_event(int(event_id))
        if deleted <= 0:
            QMessageBox.warning(self, "Eliminar evento", "No se pudo eliminar el evento.")
        self.reload_api_flow_page()

    def _configure_table(self, table, *, resize_contents: bool = True) -> None:
        header = table.horizontalHeader()
        if resize_contents:
            for column in range(8):
                header.setSectionResizeMode(column, QHeaderView.ResizeToContents)
            return
        table.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        table.verticalHeader().setDefaultSectionSize(34)

    def _refresh_resource_labels(self) -> None:
        import os

        app_stats = self.resource_monitor.read_usage(os.getpid())
        app_text = self.resource_monitor.format_usage("App", app_stats)
        self.app_resource_label.setText(app_text)

        proxy_pid = None
        session = self.api_flow_runtime.capture_manager.current_session()
        if session is not None:
            proxy_pid = session.pid
        proxy_stats = self.resource_monitor.read_usage(proxy_pid) if proxy_pid else None
        proxy_text = self.resource_monitor.format_usage("Proxy", proxy_stats)
        self.proxy_resource_label.setText(proxy_text)

    def _sync_capture_button(self) -> None:
        if self.api_flow_runtime.is_capture_running():
            self.api_flow_capture_button.setText("Detener captura")
        else:
            self.api_flow_capture_button.setText("Iniciar captura")

    @Slot(int)
    def _on_inspect_requested(self, row: int) -> None:
        payload = self.api_flow_table_model.row_at(row)
        if payload is None:
            return
        self.open_battle_inspector(payload.battle_replay_id)

    @Slot(int)
    def _on_delete_requested(self, row: int) -> None:
        payload = self.api_flow_table_model.row_at(row)
        if payload is None:
            return
        self.delete_api_flow_event(payload.api_flow_event_id, payload.battle_id_label)

    def open_battle_inspector(self, battle_replay_id: int | None) -> None:
        if battle_replay_id is None:
            return
        detail = self.api_flow_list_service.get_battle_detail(int(battle_replay_id))
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
        self.api_flow_runtime.close()
        super().closeEvent(event)

    @Slot(dict)
    def _on_runtime_state_changed(self, payload: dict) -> None:
        state = ApiFlowRuntimeState(**payload)
        if (
            state.capture_running
            and state.session_host
            and state.session_port
            and (
                state.capture_status.startswith("Captura activa")
                or state.capture_status.startswith("Passthrough hosts:")
            )
        ):
            self.api_flow_status_label.setText(
                f"Estado: activo en {state.session_host}:{state.session_port}"
            )
        else:
            self.api_flow_status_label.setText(f"Estado: {state.capture_status}")
        self.api_flow_sync_label.setText(f"Historial: {state.startup_sync_status}")
        self.api_flow_counter_label.setText(f"Eventos (sesion): {state.live_event_count}")
        self.api_flow_session_label.setText(f"Sesion: {state.session_id}")
        self._sync_capture_button()
