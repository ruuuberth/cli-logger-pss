from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.services.game_data import GameFile, detect_game_directory, scan_game_files
from app.services.storage import Storage


class MainWindow(QMainWindow):
    def __init__(self, storage: Storage):
        super().__init__()
        self.storage = storage
        self.current_dir: Path | None = None
        self.current_files: list[GameFile] = []

        self.setWindowTitle("PixelStarships Logger Native")
        self.resize(1100, 720)

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

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Archivo", "Ruta relativa", "Tamano (bytes)"])
        self.table.horizontalHeader().setStretchLastSection(True)

        top_buttons = QHBoxLayout()
        top_buttons.addWidget(self.detect_button)
        top_buttons.addWidget(self.pick_button)
        top_buttons.addWidget(self.scan_button)
        top_buttons.addWidget(self.import_button)

        content = QVBoxLayout()
        content.addLayout(top_buttons)
        content.addWidget(self.status_label)
        content.addWidget(self.files_label)
        content.addWidget(self.table)

        root = QWidget()
        root.setLayout(content)
        self.setCentralWidget(root)

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
        self._render_table(files)

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

    def _render_table(self, files: list[GameFile]) -> None:
        self.table.setRowCount(len(files))
        for idx, game_file in enumerate(files):
            self.table.setItem(idx, 0, QTableWidgetItem(game_file.name))
            self.table.setItem(idx, 1, QTableWidgetItem(game_file.relative_path))
            self.table.setItem(idx, 2, QTableWidgetItem(str(game_file.size)))
