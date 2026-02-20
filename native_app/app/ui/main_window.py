from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.services.catalog_service import CatalogService
from app.services.game_data import GameFile, detect_game_directory, scan_game_files
from app.services.storage import Storage


class MainWindow(QMainWindow):
    def __init__(self, storage: Storage, catalog_service: CatalogService):
        super().__init__()
        self.storage = storage
        self.catalog_service = catalog_service
        self.current_dir: Path | None = None
        self.current_files: list[GameFile] = []

        self.setWindowTitle("PixelStarships Logger Native")
        self.resize(1200, 760)

        tabs = QTabWidget()
        tabs.addTab(self._build_import_tab(), "Importacion local")
        tabs.addTab(self._build_catalog_tab(), "Catalogos")
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

        self.load_items_button = QPushButton("Cargar Items")
        self.load_items_button.clicked.connect(lambda: self.load_catalog("items"))
        self.load_ships_button = QPushButton("Cargar Ships")
        self.load_ships_button.clicked.connect(lambda: self.load_catalog("ships"))
        self.load_crews_button = QPushButton("Cargar Crews")
        self.load_crews_button.clicked.connect(lambda: self.load_catalog("crews"))

        self.catalog_table = QTableWidget(0, 5)
        self.catalog_table.setHorizontalHeaderLabels(["ID", "Nombre", "Tipo/Rol", "Rarity/Race", "Descripcion"])
        self.catalog_table.horizontalHeader().setStretchLastSection(True)

        buttons = QHBoxLayout()
        buttons.addWidget(self.load_items_button)
        buttons.addWidget(self.load_ships_button)
        buttons.addWidget(self.load_crews_button)
        buttons.addWidget(self.force_refresh_checkbox)

        content.addLayout(buttons)
        content.addWidget(self.catalog_status_label)
        content.addWidget(self.catalog_count_label)
        content.addWidget(self.catalog_table)
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

    def load_catalog(self, entity: str) -> None:
        force_refresh = self.force_refresh_checkbox.isChecked()
        self.catalog_status_label.setText(f"Entidad: {entity} | Cargando...")

        try:
            if entity == "items":
                rows = self.catalog_service.get_items(force_refresh=force_refresh)
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

        self.catalog_status_label.setText(f"Entidad: {entity}")
        self.catalog_count_label.setText(f"Registros: {len(rows)}")
        self._render_catalog_table(entity, rows)

    def _render_import_table(self, files: list[GameFile]) -> None:
        self.import_table.setRowCount(len(files))
        for idx, game_file in enumerate(files):
            self.import_table.setItem(idx, 0, QTableWidgetItem(game_file.name))
            self.import_table.setItem(idx, 1, QTableWidgetItem(game_file.relative_path))
            self.import_table.setItem(idx, 2, QTableWidgetItem(str(game_file.size)))

    def _render_catalog_table(self, entity: str, rows: list[dict]) -> None:
        self.catalog_table.setRowCount(len(rows))

        for idx, row in enumerate(rows):
            if entity == "items":
                col_id = row.get("item_design_id")
                col_type = row.get("item_type")
                col_meta = row.get("rarity")
            elif entity == "ships":
                col_id = row.get("ship_design_id")
                col_type = row.get("class_type")
                col_meta = row.get("rarity")
            else:
                col_id = row.get("crew_design_id")
                col_type = row.get("role")
                col_meta = row.get("race")

            self.catalog_table.setItem(idx, 0, QTableWidgetItem(str(col_id or "-")))
            self.catalog_table.setItem(idx, 1, QTableWidgetItem(str(row.get("name") or "-")))
            self.catalog_table.setItem(idx, 2, QTableWidgetItem(str(col_type or "-")))
            self.catalog_table.setItem(idx, 3, QTableWidgetItem(str(col_meta or "-")))
            self.catalog_table.setItem(idx, 4, QTableWidgetItem(str(row.get("description") or "-")))
