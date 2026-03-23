from __future__ import annotations

import os
import sys
from pathlib import Path
from types import ModuleType

try:
    from PySide6.QtWidgets import QApplication as _QtAppProbe  # noqa: F401
except (ModuleNotFoundError, ImportError):
    pyside6 = ModuleType("PySide6")
    qtwidgets = ModuleType("PySide6.QtWidgets")

    class _DummyApp:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def exec(self) -> int:
            return 0

    qtwidgets.QApplication = _DummyApp
    pyside6.QtWidgets = qtwidgets
    sys.modules["PySide6"] = pyside6
    sys.modules["PySide6.QtWidgets"] = qtwidgets

import app.main as main_module


def test_configure_environment_sets_default_sqlite_url(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(main_module, "dotenv_values", lambda *_args, **_kwargs: {})

    path = main_module.configure_environment()

    assert path == (Path.home() / ".pss_logger" / "pss_logger.db").resolve()
    assert os.environ["DATABASE_URL"] == f"sqlite:///{path}"
    assert path.parent.exists()


def test_main_initializes_db_and_starts_event_loop(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'smoke.db').resolve()}")

    calls: list[str] = []
    shown = {"value": False}

    class _DummyApp:
        def __init__(self, _argv) -> None:
            calls.append("QApplication.__init__")

        def exec(self) -> int:
            calls.append("QApplication.exec")
            return 0

    class _DummyWindow:
        def show(self) -> None:
            shown["value"] = True
            calls.append("MainWindow.show")

    db_module = ModuleType("app.models.database")
    db_module.Base = type(
        "Base",
        (),
        {
            "metadata": type(
                "Metadata",
                (),
                {"create_all": staticmethod(lambda bind=None: calls.append("Base.metadata.create_all"))},
            )()
        },
    )
    db_module.engine = object()
    db_module.ensure_sqlite_schema = lambda: calls.append("ensure_sqlite_schema")
    db_module.ensure_sqlite_indexes = lambda: calls.append("ensure_sqlite_indexes")
    db_module.log_schema_health = lambda: calls.append("log_schema_health")

    ui_module = ModuleType("app.ui.main_window")
    ui_module.MainWindow = _DummyWindow

    monkeypatch.setitem(sys.modules, "app.models.database", db_module)
    monkeypatch.setitem(sys.modules, "app.ui.main_window", ui_module)
    monkeypatch.setattr(main_module, "QApplication", _DummyApp)

    exit_code = main_module.main()

    assert exit_code == 0
    assert shown["value"] is True
    assert "Base.metadata.create_all" in calls
    assert "ensure_sqlite_schema" in calls
    assert "ensure_sqlite_indexes" in calls
    assert "log_schema_health" in calls
    assert calls[-1] == "QApplication.exec"
