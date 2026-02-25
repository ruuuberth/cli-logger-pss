from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import QObject, QSettings, QThread, QTimer, Qt, Signal, Slot
from PySide6.QtGui import QCloseEvent

from app.services.catalog_service import CatalogService
from app.services.game_data import GameFile, detect_game_directory, scan_game_files
from app.services.storage import Storage


class ItemsLoadWorker(QObject):
    finished = Signal(list, str, str)
    failed = Signal(str, str)

    def __init__(self, item_type: str, source: str, source_label: str):
        super().__init__()
        self.item_type = item_type
        self.source = source
        self.source_label = source_label

    @Slot()
    def run(self) -> None:
        try:
            service = CatalogService()
            if self.item_type == "Resources":
                rows = (
                    service.get_items(item_type="Gas", source=self.source)
                    + service.get_items(item_type="Mineral", source=self.source)
                )
            else:
                rows = service.get_items(item_type=self.item_type, source=self.source)
            self.finished.emit(rows, self.item_type, self.source_label)
        except Exception as exc:
            self.failed.emit(self.item_type, str(exc))


class ItemsFilterWorker(QObject):
    finished = Signal(list, int)
    failed = Signal(str, int)

    def __init__(
        self,
        rows: list[dict],
        criteria: dict,
        sort_key: str,
        descending: bool,
        request_id: int,
    ):
        super().__init__()
        self.rows = rows
        self.criteria = criteria
        self.sort_key = sort_key
        self.descending = descending
        self.request_id = request_id

    @staticmethod
    def _as_number(value: object) -> float | None:
        if value is None or value == "":
            return None
        if isinstance(value, bool):
            return float(int(value))
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(str(value))
        except ValueError:
            return None

    @Slot()
    def run(self) -> None:
        try:
            filtered = self.rows

            subtype = self.criteria["subtype"]
            rarity = self.criteria["rarity"]
            module = self.criteria["module"]
            level_min = self.criteria["level_min"]
            level_max = self.criteria["level_max"]
            query = self.criteria["query"]
            tag_query = self.criteria["tag_query"]
            require_ingredients = self.criteria["require_ingredients"]

            if subtype and subtype != "Todos":
                filtered = [
                    row
                    for row in filtered
                    if str(row.get("item_sub_type") or "").strip() == subtype
                ]
            if rarity and rarity != "Todas":
                filtered = [
                    row
                    for row in filtered
                    if str(row.get("rarity") or "").strip() == rarity
                ]
            if module and module != "Todos":
                filtered = [
                    row
                    for row in filtered
                    if str(row.get("module_type") or "").strip() == module
                ]
            if level_min or level_max:
                filtered_rows = []
                for row in filtered:
                    level_val = self._as_number(row.get("level"))
                    if level_val is None:
                        continue
                    if level_min and level_val < level_min:
                        continue
                    if level_max and level_val > level_max:
                        continue
                    filtered_rows.append(row)
                filtered = filtered_rows
            if query:
                filtered = [
                    row
                    for row in filtered
                    if query in str(row.get("name") or "").lower()
                    or query in str(row.get("description") or "").lower()
                ]
            if tag_query:
                filtered = [
                    row
                    for row in filtered
                    if tag_query in str(row.get("tags") or "").lower()
                ]
            if require_ingredients:
                filtered = [
                    row
                    for row in filtered
                    if str(row.get("ingredients") or "").strip()
                ]

            sort_key = self.sort_key

            def key_fn(row: dict) -> tuple[int, object]:
                value = row.get(sort_key)
                if sort_key == "item_design_id":
                    value = row.get("item_design_id") or row.get("id")
                numeric = self._as_number(value)
                if numeric is not None:
                    return (0, numeric)
                text = str(value or "").lower()
                return (1, text)

            sorted_rows = sorted(filtered, key=key_fn, reverse=self.descending)
            self.finished.emit(sorted_rows, self.request_id)
        except Exception as exc:
            self.failed.emit(str(exc), self.request_id)


class MainWindow(QMainWindow):
    def __init__(self, storage: Storage, catalog_service: CatalogService):
        super().__init__()
        self.storage = storage
        self.catalog_service = catalog_service
        self.current_dir: Path | None = None
        self.current_files: list[GameFile] = []
        self.catalog_rows: list[dict] = []
        self.catalog_page = 0
        self.catalog_page_size = 200
        self.settings = QSettings("pss-logger", "pss-native")
        self.items_worker_thread: QThread | None = None
        self.items_worker: ItemsLoadWorker | None = None
        self.items_loading = False
        self.items_filter_thread: QThread | None = None
        self.items_filter_worker: ItemsFilterWorker | None = None
        self.items_filter_request_id = 0
        self.items_filter_preserve_page: dict[int, bool] = {}
        self.items_filter_pending = False
        self.items_filtering = False
        self.items_filter_timer = QTimer(self)
        self.items_filter_timer.setSingleShot(True)
        self.items_filter_timer.timeout.connect(self._start_items_filter_worker)

        self.setWindowTitle("PixelStarships Logger Native")
        self.resize(1200, 760)

        tabs = QTabWidget()
        tabs.addTab(self._build_import_tab(), "Importacion local")
        tabs.addTab(self._build_catalog_tab(), "Catalogos")
        tabs.addTab(self._build_items_tab(), "Items")
        self.setCentralWidget(tabs)

    def _build_import_tab(self) -> QWidget:
        tab = QWidget()
        content = QVBoxLayout()

        self.status_label = QLabel("Directorio: -")
        self.files_label = QLabel("Archivos: 0")

        self.detect_button = QPushButton("Detectar carpeta automaticamente")
        self.detect_button.clicked.connect(self.detect_directory)

        self.pick_button = QPushButton("Seleccionar carpeta manualmente")
        self.pick_button.clicked.connect(self.pick_directory)

        self.scan_button = QPushButton("Escanear")
        self.scan_button.clicked.connect(self.scan_directory)

        self.import_button = QPushButton("Importar a SQLite")
        self.import_button.clicked.connect(self.import_files)

        self.import_table = QTableWidget(0, 3)
        self.import_table.setHorizontalHeaderLabels(["Archivo", "Ruta relativa", "Tamano (bytes)"])
        self.import_table.horizontalHeader().setStretchLastSection(True)

        top_buttons = QHBoxLayout()
        top_buttons.addWidget(self.detect_button)
        top_buttons.addWidget(self.pick_button)
        top_buttons.addWidget(self.scan_button)
        top_buttons.addWidget(self.import_button)

        content.addLayout(top_buttons)
        content.addWidget(self.status_label)
        content.addWidget(self.files_label)
        content.addWidget(self.import_table)
        tab.setLayout(content)
        return tab

    def _build_catalog_tab(self) -> QWidget:
        tab = QWidget()
        content = QVBoxLayout()

        self.catalog_status_label = QLabel("Entidad: -")
        self.catalog_count_label = QLabel("Registros: 0")
        self.force_refresh_checkbox = QCheckBox("Forzar refresco desde API oficial")

        self.load_ships_button = QPushButton("Cargar Ships")
        self.load_ships_button.clicked.connect(lambda: self.load_catalog("ships"))
        self.load_crews_button = QPushButton("Cargar Crews")
        self.load_crews_button.clicked.connect(lambda: self.load_catalog("crews"))

        self.catalog_columns: list[tuple[str, str]] = []
        self.catalog_table = QTableWidget(0, 5)
        self.catalog_table.setHorizontalHeaderLabels(["ID", "Nombre", "Tipo/Rol", "Rarity/Race", "Descripcion"])
        self.catalog_table.horizontalHeader().setStretchLastSection(True)
        self.catalog_table.setSortingEnabled(True)
        self.catalog_table.sortItems(0)

        self.prev_page_button = QPushButton("Anterior")
        self.prev_page_button.clicked.connect(self.prev_page)
        self.next_page_button = QPushButton("Siguiente")
        self.next_page_button.clicked.connect(self.next_page)
        self.page_label = QLabel("Pagina: 1")

        pagination = QHBoxLayout()
        pagination.addWidget(self.prev_page_button)
        pagination.addWidget(self.next_page_button)
        pagination.addWidget(self.page_label)
        pagination.addStretch()

        buttons = QHBoxLayout()
        buttons.addWidget(self.load_ships_button)
        buttons.addWidget(self.load_crews_button)
        buttons.addWidget(self.force_refresh_checkbox)

        content.addLayout(buttons)
        content.addLayout(pagination)
        content.addWidget(self.catalog_status_label)
        content.addWidget(self.catalog_count_label)
        content.addWidget(self.catalog_table)
        tab.setLayout(content)
        return tab

    def _build_items_tab(self) -> QWidget:
        tab = QWidget()
        content = QVBoxLayout()

        self.items_status_label = QLabel("Items: -")
        self.items_count_label = QLabel("Registros: 0")
        self.items_source_combo = QComboBox()
        self.items_source_combo.addItems(["BaseDeDatos", "API", "ArchivosLocales"])
        self.items_search_input = QLineEdit()
        self.items_search_input.setPlaceholderText("Buscar por nombre o descripcion...")
        self.items_search_input.textChanged.connect(self.apply_items_filters)
        self.items_subtype_combo = QComboBox()
        self.items_subtype_combo.addItem("Todos")
        self.items_subtype_combo.currentTextChanged.connect(self.apply_items_filters)
        self.items_filters_button = QToolButton()
        self.items_filters_button.setText("Filtros")
        self.items_filters_button.setCheckable(True)
        self.items_filters_button.setChecked(
            self.settings.value("items/filters_open", "false") == "true"
        )
        self.items_filters_button.toggled.connect(self._toggle_items_filters_panel)

        self.items_rarity_combo = QComboBox()
        self.items_rarity_combo.addItem("Todas")
        self.items_rarity_combo.currentTextChanged.connect(self.apply_items_filters)
        self.items_module_combo = QComboBox()
        self.items_module_combo.addItem("Todos")
        self.items_module_combo.currentTextChanged.connect(self.apply_items_filters)
        self.items_tag_input = QLineEdit()
        self.items_tag_input.setPlaceholderText("Tag...")
        self.items_tag_input.textChanged.connect(self.apply_items_filters)
        self.items_level_min = QSpinBox()
        self.items_level_min.setRange(0, 999)
        self.items_level_min.setPrefix("Min ")
        self.items_level_min.valueChanged.connect(self.apply_items_filters)
        self.items_level_max = QSpinBox()
        self.items_level_max.setRange(0, 999)
        self.items_level_max.setPrefix("Max ")
        self.items_level_max.valueChanged.connect(self.apply_items_filters)
        self.items_with_ingredients_checkbox = QCheckBox("Solo con ingredientes")
        self.items_with_ingredients_checkbox.stateChanged.connect(self.apply_items_filters)
        self.items_reset_filters_button = QPushButton("Limpiar filtros")
        self.items_reset_filters_button.clicked.connect(self.reset_items_filters)

        self.load_items_missile_button = QPushButton("Misiles")
        self.load_items_missile_button.clicked.connect(
            lambda: self.load_items("Missile")
        )
        self.load_items_craft_button = QPushButton("Craft")
        self.load_items_craft_button.clicked.connect(
            lambda: self.load_items("Craft")
        )
        self.load_items_equipment_button = QPushButton("Equipamiento")
        self.load_items_equipment_button.clicked.connect(
            lambda: self.load_items("Equipment")
        )
        self.load_items_android_button = QPushButton("Android")
        self.load_items_android_button.clicked.connect(
            lambda: self.load_items("Android")
        )
        self.load_items_resources_button = QPushButton("Recursos")
        self.load_items_resources_button.clicked.connect(
            lambda: self.load_items("Resources")
        )

        self.items_columns: list[tuple[str, str]] = []
        self.items_table = QTableWidget(0, 5)
        self.items_table.setHorizontalHeaderLabels(["ID", "Nombre", "Tipo", "Rarity", "Descripcion"])
        self.items_table.horizontalHeader().setStretchLastSection(True)
        self.items_table.setSortingEnabled(False)
        self.items_table.horizontalHeader().setSortIndicatorShown(True)
        self.items_table.horizontalHeader().sectionClicked.connect(self._items_sort_by_column)
        self.items_sort_column = 0
        self.items_sort_order = Qt.AscendingOrder

        self.items_prev_page_button = QPushButton("Anterior")
        self.items_prev_page_button.clicked.connect(self.items_prev_page)
        self.items_next_page_button = QPushButton("Siguiente")
        self.items_next_page_button.clicked.connect(self.items_next_page)
        self.items_page_label = QLabel("Pagina: 1")

        self.items_rows: list[dict] = []
        self.items_filtered_rows: list[dict] = []
        self.items_page = 0
        self.items_page_size = 200

        buttons = QHBoxLayout()
        buttons.addWidget(self.load_items_missile_button)
        buttons.addWidget(self.load_items_craft_button)
        buttons.addWidget(self.load_items_equipment_button)
        buttons.addWidget(self.load_items_android_button)
        buttons.addWidget(self.load_items_resources_button)
        buttons.addWidget(self.items_search_input)
        buttons.addWidget(QLabel("Fuente"))
        buttons.addWidget(self.items_source_combo)
        buttons.addWidget(QLabel("SubTipo"))
        buttons.addWidget(self.items_subtype_combo)
        buttons.addWidget(self.items_filters_button)

        self.items_filters_panel = QWidget()
        filters_layout = QHBoxLayout()
        filters_layout.setContentsMargins(0, 0, 0, 0)
        filters_layout.addWidget(QLabel("Rarity"))
        filters_layout.addWidget(self.items_rarity_combo)
        filters_layout.addWidget(QLabel("Modulo"))
        filters_layout.addWidget(self.items_module_combo)
        filters_layout.addWidget(QLabel("Nivel"))
        filters_layout.addWidget(self.items_level_min)
        filters_layout.addWidget(self.items_level_max)
        filters_layout.addWidget(QLabel("Tag"))
        filters_layout.addWidget(self.items_tag_input)
        filters_layout.addWidget(self.items_with_ingredients_checkbox)
        filters_layout.addWidget(self.items_reset_filters_button)
        filters_layout.addStretch()
        self.items_filters_panel.setLayout(filters_layout)
        self.items_filters_panel.setVisible(self.items_filters_button.isChecked())

        pagination = QHBoxLayout()
        pagination.addWidget(self.items_prev_page_button)
        pagination.addWidget(self.items_next_page_button)
        pagination.addWidget(self.items_page_label)
        pagination.addStretch()

        content.addLayout(buttons)
        content.addWidget(self.items_filters_panel)
        content.addLayout(pagination)
        content.addWidget(self.items_status_label)
        content.addWidget(self.items_count_label)
        content.addWidget(self.items_table)
        tab.setLayout(content)
        return tab

    def detect_directory(self) -> None:
        detected = detect_game_directory()
        if not detected:
            QMessageBox.warning(self, "No encontrado", "No se detecto automaticamente la carpeta SavySoda/Pixel Starships.")
            return
        self.current_dir = detected
        self.status_label.setText(f"Directorio: {detected}")

    def pick_directory(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Selecciona carpeta SavySoda/Pixel Starships")
        if not directory:
            return
        self.current_dir = Path(directory)
        self.status_label.setText(f"Directorio: {directory}")

    def scan_directory(self) -> None:
        if not self.current_dir:
            QMessageBox.information(self, "Sin directorio", "Primero detecta o selecciona una carpeta.")
            return

        files = scan_game_files(self.current_dir)
        self.current_files = files
        self.files_label.setText(f"Archivos: {len(files)}")
        self._render_import_table(files)

        if not files:
            QMessageBox.information(self, "Sin resultados", "No se encontraron archivos exportables en la carpeta seleccionada.")

    def import_files(self) -> None:
        if not self.current_dir:
            QMessageBox.information(self, "Sin directorio", "Primero detecta o selecciona una carpeta.")
            return
        if not self.current_files:
            QMessageBox.information(self, "Sin archivos", "Primero escanea la carpeta.")
            return

        result = self.storage.import_files(str(self.current_dir), self.current_files)
        QMessageBox.information(
            self,
            "Importacion completada",
            f"Total: {result['total']} | Nuevos: {result['imported']} | Actualizados: {result['updated']}",
        )

    def load_catalog(self, entity: str, item_type: str | None = None) -> None:
        force_refresh = self.force_refresh_checkbox.isChecked()
        status = f"Entidad: {entity}"
        if item_type:
            status += f" ({item_type})"
        self.catalog_status_label.setText(f"{status} | Cargando...")

        try:
            self._set_catalog_columns(entity)
            if entity == "items":
                rows = self.catalog_service.get_items(force_refresh=force_refresh, item_type=item_type)
            elif entity == "ships":
                rows = self.catalog_service.get_ships(force_refresh=force_refresh)
            elif entity == "crews":
                rows = self.catalog_service.get_crews(force_refresh=force_refresh)
            else:
                rows = []
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"No se pudo cargar {entity}: {exc}")
            self.catalog_status_label.setText(f"Entidad: {entity} | Error")
            return

        self.catalog_status_label.setText(status)
        self.catalog_rows = rows
        self.catalog_page = 0
        self._render_current_page(entity)

    def load_items(self, item_type: str) -> None:
        if self.items_loading:
            self.items_status_label.setText("Items: carga en progreso...")
            return

        selected_source = self.items_source_combo.currentText()
        source = "db"
        if selected_source == "API":
            source = "api"
        elif selected_source == "ArchivosLocales":
            source = "local"
        if item_type == "Resources":
            status_label = "Items: Recursos"
        else:
            status_label = f"Items: {item_type}"
        self.items_status_label.setText(f"{status_label} | Cargando ({selected_source})...")
        self._set_items_loading_state(True)

        self.items_worker_thread = QThread(self)
        self.items_worker = ItemsLoadWorker(item_type=item_type, source=source, source_label=selected_source)
        self.items_worker.moveToThread(self.items_worker_thread)

        self.items_worker_thread.started.connect(self.items_worker.run)
        self.items_worker.finished.connect(self._on_items_loaded)
        self.items_worker.failed.connect(self._on_items_load_failed)
        self.items_worker.finished.connect(self.items_worker_thread.quit)
        self.items_worker.failed.connect(self.items_worker_thread.quit)
        self.items_worker_thread.finished.connect(self._on_items_worker_finished)
        self.items_worker_thread.finished.connect(self.items_worker.deleteLater)
        self.items_worker_thread.finished.connect(self.items_worker_thread.deleteLater)
        self.items_worker_thread.start()

    @Slot(list, str, str)
    def _on_items_loaded(self, rows: list[dict], item_type: str, source_label: str) -> None:
        if item_type == "Resources":
            status_label = "Items: Recursos"
        else:
            status_label = f"Items: {item_type}"
        self.items_status_label.setText(f"{status_label} | Fuente: {source_label}")
        self.items_rows = rows
        self._set_items_columns()
        self._refresh_items_subtypes()
        self._refresh_items_filters()
        self._restore_items_filter_state()
        self.items_page = 0
        self.apply_items_filters()

    @Slot(str, str)
    def _on_items_load_failed(self, item_type: str, error_message: str) -> None:
        if item_type == "Resources":
            status_label = "Items: Recursos"
        else:
            status_label = f"Items: {item_type}"
        QMessageBox.critical(self, "Error", f"No se pudo cargar items {item_type}: {error_message}")
        self.items_status_label.setText(f"{status_label} | Error")

    @Slot()
    def _on_items_worker_finished(self) -> None:
        self.items_worker = None
        self.items_worker_thread = None
        self._set_items_loading_state(False)
        self.apply_items_filters()

    def _set_items_loading_state(self, loading: bool) -> None:
        self.items_loading = loading
        self.load_items_missile_button.setEnabled(not loading)
        self.load_items_craft_button.setEnabled(not loading)
        self.load_items_equipment_button.setEnabled(not loading)
        self.load_items_android_button.setEnabled(not loading)
        self.load_items_resources_button.setEnabled(not loading)
        self.items_source_combo.setEnabled(not loading)
        self.items_search_input.setEnabled(not loading)
        self.items_subtype_combo.setEnabled(not loading)
        self.items_filters_button.setEnabled(not loading)
        self.items_rarity_combo.setEnabled(not loading)
        self.items_module_combo.setEnabled(not loading)
        self.items_tag_input.setEnabled(not loading)
        self.items_level_min.setEnabled(not loading)
        self.items_level_max.setEnabled(not loading)
        self.items_with_ingredients_checkbox.setEnabled(not loading)
        self.items_reset_filters_button.setEnabled(not loading)
        self.items_prev_page_button.setEnabled(not loading and not self.items_filtering)
        self.items_next_page_button.setEnabled(not loading and not self.items_filtering)

    def _set_items_filtering_state(self, filtering: bool) -> None:
        self.items_filtering = filtering
        can_page = not self.items_loading and not filtering
        self.items_prev_page_button.setEnabled(can_page)
        self.items_next_page_button.setEnabled(can_page)

    def _render_import_table(self, files: list[GameFile]) -> None:
        self.import_table.setRowCount(len(files))
        for idx, game_file in enumerate(files):
            self.import_table.setItem(idx, 0, QTableWidgetItem(game_file.name))
            self.import_table.setItem(idx, 1, QTableWidgetItem(game_file.relative_path))
            self.import_table.setItem(idx, 2, QTableWidgetItem(str(game_file.size)))

    def _render_catalog_table(self, entity: str, rows: list[dict]) -> None:
        sorting_enabled = self.catalog_table.isSortingEnabled()
        if sorting_enabled:
            self.catalog_table.setSortingEnabled(False)
        self.catalog_table.setRowCount(len(rows))

        for idx, row in enumerate(rows):
            for col_idx, (_, key) in enumerate(self.catalog_columns):
                value = row.get(key)
                if key == "item_design_id":
                    value = row.get("item_design_id") or row.get("id")
                elif key == "ship_design_id":
                    value = row.get("ship_design_id") or row.get("id")
                elif key == "crew_design_id":
                    value = row.get("crew_design_id") or row.get("id")
                self.catalog_table.setItem(idx, col_idx, QTableWidgetItem(str(value or "-")))
        if sorting_enabled:
            self.catalog_table.setSortingEnabled(True)

    def _render_items_table(self, rows: list[dict]) -> None:
        sorting_enabled = self.items_table.isSortingEnabled()
        if sorting_enabled:
            self.items_table.setSortingEnabled(False)
        self.items_table.setRowCount(len(rows))
        for idx, row in enumerate(rows):
            for col_idx, (_, key) in enumerate(self.items_columns):
                value = row.get(key)
                if key == "item_design_id":
                    value = row.get("item_design_id") or row.get("id")
                item = QTableWidgetItem(str(value or "-"))
                numeric_value = self._as_number(value)
                if numeric_value is not None:
                    item.setData(0, numeric_value)
                self.items_table.setItem(idx, col_idx, item)
        if sorting_enabled:
            self.items_table.setSortingEnabled(True)

    def _render_current_page(self, entity: str) -> None:
        total = len(self.catalog_rows)
        if total == 0:
            self.catalog_count_label.setText("Registros: 0")
            self.page_label.setText("Pagina: 0")
            self.catalog_table.setRowCount(0)
            return

        start = self.catalog_page * self.catalog_page_size
        end = min(start + self.catalog_page_size, total)
        page_rows = self.catalog_rows[start:end]
        self.catalog_count_label.setText(f"Registros: {total} | Mostrando {start + 1}-{end}")
        self.page_label.setText(f"Pagina: {self.catalog_page + 1}")
        self._render_catalog_table(entity, page_rows)

    def _render_items_page(self) -> None:
        total = len(self.items_filtered_rows)
        base_total = len(self.items_rows)
        if total == 0:
            self.items_count_label.setText(f"Registros: 0 de {base_total}")
            self.items_page_label.setText("Pagina: 0")
            self.items_table.setRowCount(0)
            self.items_prev_page_button.setEnabled(False)
            self.items_next_page_button.setEnabled(False)
            return

        start = self.items_page * self.items_page_size
        end = min(start + self.items_page_size, total)
        page_rows = self.items_filtered_rows[start:end]
        self.items_count_label.setText(
            f"Registros: {total} de {base_total} | Mostrando {start + 1}-{end}"
        )
        self.items_page_label.setText(f"Pagina: {self.items_page + 1}")
        self._render_items_table(page_rows)
        self._save_items_filter_state()
        max_page = (total - 1) // self.items_page_size
        can_page = not self.items_loading and not self.items_filtering
        self.items_prev_page_button.setEnabled(can_page and self.items_page > 0)
        self.items_next_page_button.setEnabled(can_page and self.items_page < max_page)

    def next_page(self) -> None:
        total = len(self.catalog_rows)
        if total == 0:
            return
        max_page = (total - 1) // self.catalog_page_size
        if self.catalog_page < max_page:
            self.catalog_page += 1
            entity = self._current_entity()
            self._render_current_page(entity)

    def prev_page(self) -> None:
        if self.catalog_page > 0:
            self.catalog_page -= 1
            entity = self._current_entity()
            self._render_current_page(entity)

    def items_next_page(self) -> None:
        total = len(self.items_filtered_rows)
        if total == 0:
            return
        max_page = (total - 1) // self.items_page_size
        if self.items_page < max_page:
            self.items_page += 1
            self._render_items_page()

    def items_prev_page(self) -> None:
        if self.items_page > 0:
            self.items_page -= 1
            self._render_items_page()

    def _current_entity(self) -> str:
        status = self.catalog_status_label.text()
        if "items" in status:
            return "items"
        if "ships" in status:
            return "ships"
        if "crews" in status:
            return "crews"
        return "items"

    def _set_catalog_columns(self, entity: str) -> None:
        if entity == "items":
            self.catalog_columns = [
                ("ID", "item_design_id"),
                ("Nombre", "name"),
                ("Tipo", "item_type"),
                ("Rarity", "rarity"),
                ("Level", "level"),
                ("SubType", "item_sub_type"),
                ("MinShip", "min_ship_level"),
                ("MinRoom", "min_room_level"),
                ("MarketPrice", "market_price"),
                ("FairPrice", "fair_price"),
                ("BuildTime", "build_time"),
                ("MineralCost", "mineral_cost"),
                ("GasCost", "gas_cost"),
                ("ManufactureCost", "manufacture_cost"),
                ("StarbaseCost", "starbase_manufacture_cost"),
                ("OurPrice", "our_price"),
                ("ModuleType", "module_type"),
                ("ModuleArg", "module_argument"),
                ("EnhType", "enhancement_type"),
                ("EnhValue", "enhancement_value"),
                ("DropChance", "drop_chance"),
                ("MaxCount", "max_count"),
                ("ItemSpace", "item_space"),
                ("ReqResearchId", "required_research_design_id"),
                ("Tags", "tags"),
                ("Ingredients", "ingredients"),
                ("Metadata", "metadata_json"),
                ("Descripcion", "description"),
            ]
        elif entity == "ships":
            self.catalog_columns = [
                ("ID", "ship_design_id"),
                ("Nombre", "name"),
                ("Clase", "class_type"),
                ("Rarity", "rarity"),
                ("Descripcion", "description"),
            ]
        else:
            self.catalog_columns = [
                ("ID", "crew_design_id"),
                ("Nombre", "name"),
                ("Rol", "role"),
                ("Race", "race"),
                ("Descripcion", "description"),
            ]

        self.catalog_table.setColumnCount(len(self.catalog_columns))
        self.catalog_table.setHorizontalHeaderLabels([label for label, _ in self.catalog_columns])

    def _set_items_columns(self) -> None:
        self.items_columns = [
            ("ID", "item_design_id"),
            ("Nombre", "name"),
            ("Tipo", "item_type"),
            ("Rarity", "rarity"),
            ("Level", "level"),
            ("SubType", "item_sub_type"),
            ("MinShip", "min_ship_level"),
            ("MinRoom", "min_room_level"),
            ("MarketPrice", "market_price"),
            ("FairPrice", "fair_price"),
            ("BuildTime", "build_time"),
            ("MineralCost", "mineral_cost"),
            ("GasCost", "gas_cost"),
            ("ManufactureCost", "manufacture_cost"),
            ("StarbaseCost", "starbase_manufacture_cost"),
            ("OurPrice", "our_price"),
            ("ModuleType", "module_type"),
            ("ModuleArg", "module_argument"),
            ("EnhType", "enhancement_type"),
            ("EnhValue", "enhancement_value"),
            ("DropChance", "drop_chance"),
            ("MaxCount", "max_count"),
            ("ItemSpace", "item_space"),
            ("ReqResearchId", "required_research_design_id"),
            ("Tags", "tags"),
            ("Ingredients", "ingredients"),
            ("Metadata", "metadata_json"),
            ("Descripcion", "description"),
        ]

        self.items_table.setColumnCount(len(self.items_columns))
        self.items_table.setHorizontalHeaderLabels([label for label, _ in self.items_columns])

    def _refresh_items_subtypes(self) -> None:
        current = self.items_subtype_combo.currentText()
        subtypes = sorted(
            {
                str(row.get("item_sub_type") or "").strip()
                for row in self.items_rows
                if str(row.get("item_sub_type") or "").strip()
            }
        )
        self.items_subtype_combo.blockSignals(True)
        self.items_subtype_combo.clear()
        self.items_subtype_combo.addItem("Todos")
        for subtype in subtypes:
            self.items_subtype_combo.addItem(subtype)
        if current and current in subtypes:
            self.items_subtype_combo.setCurrentText(current)
        self.items_subtype_combo.blockSignals(False)

    def _refresh_items_filters(self) -> None:
        current_rarity = self.items_rarity_combo.currentText()
        current_module = self.items_module_combo.currentText()

        rarities = sorted(
            {
                str(row.get("rarity") or "").strip()
                for row in self.items_rows
                if str(row.get("rarity") or "").strip()
            }
        )
        modules = sorted(
            {
                str(row.get("module_type") or "").strip()
                for row in self.items_rows
                if str(row.get("module_type") or "").strip()
            }
        )

        self.items_rarity_combo.blockSignals(True)
        self.items_rarity_combo.clear()
        self.items_rarity_combo.addItem("Todas")
        for rarity in rarities:
            self.items_rarity_combo.addItem(rarity)
        if current_rarity and current_rarity in rarities:
            self.items_rarity_combo.setCurrentText(current_rarity)
        self.items_rarity_combo.blockSignals(False)

        self.items_module_combo.blockSignals(True)
        self.items_module_combo.clear()
        self.items_module_combo.addItem("Todos")
        for module in modules:
            self.items_module_combo.addItem(module)
        if current_module and current_module in modules:
            self.items_module_combo.setCurrentText(current_module)
        self.items_module_combo.blockSignals(False)

    def apply_items_filters(self, *_, preserve_page: bool = False) -> None:
        if self.items_loading:
            return
        self.items_filter_request_id += 1
        self.items_filter_preserve_page[self.items_filter_request_id] = preserve_page
        if len(self.items_filter_preserve_page) > 200:
            # Keep memory bounded; stale entries are not needed.
            min_id = self.items_filter_request_id - 100
            self.items_filter_preserve_page = {
                rid: keep for rid, keep in self.items_filter_preserve_page.items() if rid >= min_id
            }
        self.items_filter_pending = True
        self.items_filter_timer.start(120)

    def _current_items_filter_criteria(self) -> dict:
        return {
            "subtype": self.items_subtype_combo.currentText(),
            "rarity": self.items_rarity_combo.currentText(),
            "module": self.items_module_combo.currentText(),
            "level_min": self.items_level_min.value(),
            "level_max": self.items_level_max.value(),
            "query": self.items_search_input.text().strip().lower(),
            "tag_query": self.items_tag_input.text().strip().lower(),
            "require_ingredients": self.items_with_ingredients_checkbox.isChecked(),
        }

    @Slot()
    def _start_items_filter_worker(self) -> None:
        if self.items_loading:
            return
        if self.items_filter_thread is not None and self.items_filter_thread.isRunning():
            self.items_filter_pending = True
            return
        self.items_filter_pending = False
        request_id = self.items_filter_request_id
        criteria = self._current_items_filter_criteria()
        if not self.items_columns:
            self.items_filtered_rows = list(self.items_rows)
            self.items_page = 0
            self._render_items_page()
            return
        sort_key = self.items_columns[self.items_sort_column][1]
        descending = self.items_sort_order == Qt.DescendingOrder
        rows = list(self.items_rows)

        self._set_items_filtering_state(True)
        self.items_filter_thread = QThread(self)
        self.items_filter_worker = ItemsFilterWorker(
            rows=rows,
            criteria=criteria,
            sort_key=sort_key,
            descending=descending,
            request_id=request_id,
        )
        self.items_filter_worker.moveToThread(self.items_filter_thread)
        self.items_filter_thread.started.connect(self.items_filter_worker.run)
        self.items_filter_worker.finished.connect(self._on_items_filter_finished)
        self.items_filter_worker.failed.connect(self._on_items_filter_failed)
        self.items_filter_worker.finished.connect(self.items_filter_thread.quit)
        self.items_filter_worker.failed.connect(self.items_filter_thread.quit)
        self.items_filter_thread.finished.connect(self._on_items_filter_worker_finished)
        self.items_filter_thread.finished.connect(self.items_filter_worker.deleteLater)
        self.items_filter_thread.finished.connect(self.items_filter_thread.deleteLater)
        self.items_filter_thread.start()

    @Slot(list, int)
    def _on_items_filter_finished(self, rows: list[dict], request_id: int) -> None:
        preserve_page = self.items_filter_preserve_page.pop(request_id, False)
        if request_id != self.items_filter_request_id:
            return
        self.items_filtered_rows = rows
        if not rows:
            self.items_page = 0
        elif preserve_page:
            max_page = (len(rows) - 1) // self.items_page_size
            self.items_page = min(self.items_page, max_page)
        else:
            self.items_page = 0
        self._render_items_page()

    @Slot(str, int)
    def _on_items_filter_failed(self, error_message: str, request_id: int) -> None:
        self.items_filter_preserve_page.pop(request_id, None)
        if request_id != self.items_filter_request_id:
            return
        self.items_status_label.setText(f"{self.items_status_label.text()} | Error filtro")
        QMessageBox.critical(self, "Error", f"No se pudo filtrar items: {error_message}")

    @Slot()
    def _on_items_filter_worker_finished(self) -> None:
        self.items_filter_worker = None
        self.items_filter_thread = None
        self._set_items_filtering_state(False)
        if self.items_filter_pending:
            self.items_filter_timer.start(10)

    def _as_number(self, value: object) -> float | None:
        if value is None or value == "":
            return None
        if isinstance(value, bool):
            return float(int(value))
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(str(value))
        except ValueError:
            return None

    def _items_sort_by_column(self, column_index: int) -> None:
        if self.items_sort_column == column_index:
            self.items_sort_order = (
                Qt.DescendingOrder
                if self.items_sort_order == Qt.AscendingOrder
                else Qt.AscendingOrder
            )
        else:
            self.items_sort_column = column_index
            self.items_sort_order = Qt.AscendingOrder
        self.items_table.horizontalHeader().setSortIndicator(
            self.items_sort_column, self.items_sort_order
        )
        self.apply_items_filters(preserve_page=True)

    def _toggle_items_filters_panel(self, checked: bool) -> None:
        self.items_filters_panel.setVisible(checked)
        self.settings.setValue("items/filters_open", "true" if checked else "false")

    def reset_items_filters(self) -> None:
        self.items_search_input.setText("")
        self.items_tag_input.setText("")
        self.items_subtype_combo.setCurrentText("Todos")
        self.items_rarity_combo.setCurrentText("Todas")
        self.items_module_combo.setCurrentText("Todos")
        self.items_level_min.setValue(0)
        self.items_level_max.setValue(0)
        self.items_with_ingredients_checkbox.setChecked(False)

    def _save_items_filter_state(self) -> None:
        self.settings.setValue("items/search", self.items_search_input.text())
        self.settings.setValue("items/tag", self.items_tag_input.text())
        self.settings.setValue("items/subtype", self.items_subtype_combo.currentText())
        self.settings.setValue("items/rarity", self.items_rarity_combo.currentText())
        self.settings.setValue("items/module", self.items_module_combo.currentText())
        self.settings.setValue("items/level_min", self.items_level_min.value())
        self.settings.setValue("items/level_max", self.items_level_max.value())
        self.settings.setValue(
            "items/with_ingredients",
            "true" if self.items_with_ingredients_checkbox.isChecked() else "false",
        )

    def _restore_items_filter_state(self) -> None:
        self.items_search_input.setText(self.settings.value("items/search", ""))
        self.items_tag_input.setText(self.settings.value("items/tag", ""))
        self.items_subtype_combo.setCurrentText(self.settings.value("items/subtype", "Todos"))
        self.items_rarity_combo.setCurrentText(self.settings.value("items/rarity", "Todas"))
        self.items_module_combo.setCurrentText(self.settings.value("items/module", "Todos"))
        self.items_level_min.setValue(int(self.settings.value("items/level_min", 0)))
        self.items_level_max.setValue(int(self.settings.value("items/level_max", 0)))
        self.items_with_ingredients_checkbox.setChecked(
            self.settings.value("items/with_ingredients", "false") == "true"
        )

    def closeEvent(self, event: QCloseEvent) -> None:
        self.items_filter_timer.stop()
        if self.items_filter_thread is not None and self.items_filter_thread.isRunning():
            self.items_filter_thread.quit()
            self.items_filter_thread.wait(2000)
        if self.items_worker_thread is not None and self.items_worker_thread.isRunning():
            self.items_worker_thread.quit()
            self.items_worker_thread.wait(2000)
        super().closeEvent(event)
