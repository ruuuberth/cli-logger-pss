from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import dotenv_values
from PySide6.QtWidgets import QApplication
from sqlalchemy.engine import make_url


def default_db_path() -> Path:
    return Path.home() / ".pss_logger" / "pss_logger.db"


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def sqlite_db_path_from_url(database_url: str) -> Path | None:
    try:
        url = make_url(database_url)
    except Exception:
        return None

    if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:":
        return None

    db_path = Path(url.database)
    if not db_path.is_absolute():
        db_path = (project_root() / db_path).resolve()
    return db_path


def configure_environment() -> Path:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        dotenv_database_url = dotenv_values(project_root() / ".env").get("DATABASE_URL")
        if dotenv_database_url:
            database_url = str(dotenv_database_url)
            os.environ["DATABASE_URL"] = database_url

    db_path = sqlite_db_path_from_url(database_url) if database_url else None
    if db_path is None:
        db_path = default_db_path().resolve()
        os.environ.setdefault("DATABASE_URL", f"sqlite:///{db_path}")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path


def main() -> int:
    db_path = configure_environment()

    from app.models.database import (
        Base,
        backfill_item_designs_columns,
        backfill_item_relations,
        engine,
        ensure_sqlite_schema,
        ensure_sqlite_indexes,
        log_schema_health,
        migrate_item_designs_drop_raw_data,
        repair_item_designs_json_columns,
    )
    from app.services.catalog_service import CatalogService
    from app.services.storage import Storage
    from app.ui.main_window import MainWindow

    Base.metadata.create_all(bind=engine)
    ensure_sqlite_schema()
    ensure_sqlite_indexes()
    backfill_item_designs_columns()
    repair_item_designs_json_columns()
    migrate_item_designs_drop_raw_data()
    backfill_item_relations()
    log_schema_health()

    app = QApplication(sys.argv)
    storage = Storage(db_path)
    catalog_service = CatalogService()
    window = MainWindow(storage=storage, catalog_service=catalog_service)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
