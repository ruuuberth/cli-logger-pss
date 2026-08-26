from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def _resolve_log_path(base_dir: Path) -> Path:
    configured = os.environ.get("APP_LOG_PATH", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return base_dir / "pss_logger.log"


def configure_logging(base_dir: Path) -> Path:
    log_path = _resolve_log_path(base_dir)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    level_name = os.environ.get("APP_LOG_LEVEL", "INFO").upper().strip()
    level = getattr(logging, level_name, logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)

    console_handler = logging.StreamHandler(stream=sys.stderr)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(file_handler)
    root.addHandler(console_handler)

    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    logging.info("event=log_configured path=%s level=%s", log_path, level_name)
    return log_path
