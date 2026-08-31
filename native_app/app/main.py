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


def _configure_streams() -> None:
    """Force UTF-8 encoding for stdout/stderr on Windows for Unicode support.

    This function must be called early in main(), before any logging or output,
    to ensure consistent UTF-8 encoding throughout the application lifecycle.

    On Windows, the default stdout/stderr encoding is typically cp1252 or cp850,
    which cannot represent Unicode characters (emojis, international text).
    Calling reconfigure() with UTF-8 and errors='replace' ensures:

    1. All subsequent print/log output uses UTF-8 encoding
    2. Unencodable characters are replaced with '?' instead of raising UnicodeEncodeError
    2. Cross-platform consistency (Linux/macOS already default to UTF-8)

    Safety: This is called at the very start of main() before any logging,
    configuration, or user output occurs. No other code has written to
    stdout/stderr at this point, so reconfigure() is safe.

    On Python < 3.7, sys.stdout/stderr don't have reconfigure(), so we
    gracefully skip with hasattr() check. The logging system will still
    use the default encoding in that case.
    """
    for stream_name, stream in (("stdout", sys.stdout), ("stderr", sys.stderr)):
        if hasattr(stream, 'reconfigure'):
            try:
                stream.reconfigure(encoding='utf-8', errors='replace')
            except (OSError, ValueError) as e:
                # Fallback: logging not yet configured, write directly to stderr
                print(f"Warning: Failed to reconfigure {stream_name}: {e}", file=sys.__stderr__)


def main() -> int:
    db_path = configure_environment()
    from app.core.build_info import get_build_info
    from app.core.logging_setup import configure_logging

    _configure_streams()
    configure_logging(db_path.parent)
    build_info = get_build_info()
    import logging

    logging.getLogger(__name__).info(
        "event=build_info version=%s git_sha=%s build_time=%s source=%s",
        build_info.version,
        build_info.git_sha,
        build_info.build_time,
        build_info.source,
    )

    from app.models.database import (
        Base,
        engine,
        ensure_sqlite_schema,
        ensure_sqlite_indexes,
        log_schema_health,
    )
    from app.services.api_flow_runtime import ApiFlowRuntime
    from app.cli.cli_manager import CliManager

    Base.metadata.create_all(bind=engine)
    ensure_sqlite_schema()
    ensure_sqlite_indexes()
    log_schema_health()

    # Iniciar captura de tráfico automáticamente (failure-tolerant)
    runtime = ApiFlowRuntime()
    try:
        runtime.start_capture()
        logging.getLogger(__name__).info("event=capture_started status=auto_start")
    except Exception as e:
        logging.getLogger(__name__).warning(
            "event=capture_auto_start_failed error=%s message=CLI_will_continue_without_capture",
            e
        )

    # CLI runs regardless of capture initialization outcome
    try:
        cli_manager = CliManager(capture_runtime=runtime)
        cli_manager.run()
    except KeyboardInterrupt:
        logging.getLogger(__name__).info("event=app_exit status=keyboard_interrupt")
    except Exception as e:
        logging.getLogger(__name__).error(f"event=app_error error={e}")
    finally:
        logging.getLogger(__name__).info("event=app_shutdown status=cleaning_up")
        runtime.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
