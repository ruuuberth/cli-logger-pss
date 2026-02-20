from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.services.storage import Storage
from app.ui.main_window import MainWindow


def default_db_path() -> Path:
    return Path.home() / ".pss_logger" / "pss_logger.db"


def main() -> int:
    app = QApplication(sys.argv)
    storage = Storage(default_db_path())
    window = MainWindow(storage)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
