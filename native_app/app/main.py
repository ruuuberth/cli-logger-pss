from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import dotenv_values
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
    return db_path.resolve()


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
        # Construir URL SQLite con forward slashes para compatibilidad multiplataforma
        db_path_str = str(db_path).replace("\\", "/")
        os.environ.setdefault("DATABASE_URL", f"sqlite:///{db_path_str}")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path


def initialize_database(db_path: Path) -> None:
    """Inicializa la base de datos y esquema."""
    from app.models.database import (
        Base,
        engine,
        ensure_sqlite_schema,
        ensure_sqlite_indexes,
        log_schema_health,
    )

    Base.metadata.create_all(bind=engine)
    ensure_sqlite_schema()
    ensure_sqlite_indexes()
    log_schema_health()


def main_cli() -> int:
    """Modo CLI interactivo."""
    from app.cli.cli_manager import CliManager

    cli = CliManager()
    return cli.run()


def main() -> int:
    """Main entry point - CLI only."""
    db_path = configure_environment()
    from app.core.logging_setup import configure_logging

    configure_logging(db_path.parent)
    initialize_database(db_path)

    return main_cli()


if __name__ == "__main__":
    raise SystemExit(main())

