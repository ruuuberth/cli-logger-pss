from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication


def default_db_path() -> Path:
    return Path.home() / ".pss_logger" / "pss_logger.db"


def configure_environment() -> Path:
    db_path = default_db_path().resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("DATABASE_URL", f"sqlite:///{db_path}")
    return db_path


def main() -> int:
    db_path = configure_environment()

    from app.models.database import Base, engine
    from app.services.catalog_service import CatalogService
    from app.services.storage import Storage
    from app.ui.main_window import MainWindow

    Base.metadata.create_all(bind=engine)

    app = QApplication(sys.argv)
    storage = Storage(db_path)
    catalog_service = CatalogService()
    window = MainWindow(storage=storage, catalog_service=catalog_service)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
