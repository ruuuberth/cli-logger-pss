from __future__ import annotations

import logging
from pathlib import Path

import pytest
from pydantic_settings import SettingsError

from app.core.config import Settings


def test_settings_json_arrays_work_with_dotenv(
    tmp_path: Path, monkeypatch
) -> None:
    """JSON array format in .env is parsed correctly (post-fix behavior)."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("API_FLOW_IGNORE_HOSTS", raising=False)
    monkeypatch.delenv("API_FLOW_CAPTURE_HOST_ALLOWLIST", raising=False)
    monkeypatch.delenv("API_FLOW_CAPTURE_PATH_ALLOWLIST", raising=False)
    monkeypatch.chdir(tmp_path)

    (tmp_path / ".env").write_text(
        "DATABASE_URL=sqlite:///./custom.db\n"
        'API_FLOW_IGNORE_HOSTS=["one.test","two.test"]\n'
        'API_FLOW_CAPTURE_HOST_ALLOWLIST=["api.pixelstarships.com"]\n'
        'API_FLOW_CAPTURE_PATH_ALLOWLIST='
        '["/BattleService/GetBattle3","/BattleService/GetBattle3/"]\n',
        encoding="utf-8",
    )

    loaded = Settings()

    assert loaded.DATABASE_URL == "sqlite:///./custom.db"
    assert loaded.API_FLOW_IGNORE_HOSTS == ["one.test", "two.test"]
    assert loaded.API_FLOW_CAPTURE_HOST_ALLOWLIST == ["api.pixelstarships.com"]
    assert loaded.API_FLOW_CAPTURE_PATH_ALLOWLIST == [
        "/BattleService/GetBattle3",
        "/BattleService/GetBattle3/",
    ]


def test_settings_csv_raises_validation_error(
    tmp_path: Path, monkeypatch
) -> None:
    """CSV list syntax in .env raises SettingsError instead of being parsed (issue #16)."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("API_FLOW_IGNORE_HOSTS", raising=False)
    monkeypatch.delenv("API_FLOW_CAPTURE_HOST_ALLOWLIST", raising=False)
    monkeypatch.delenv("API_FLOW_CAPTURE_PATH_ALLOWLIST", raising=False)
    monkeypatch.chdir(tmp_path)

    (tmp_path / ".env").write_text(
        "DATABASE_URL=sqlite:///./custom.db\n"
        "API_FLOW_IGNORE_HOSTS=one.test,two.test\n"
        "API_FLOW_CAPTURE_HOST_ALLOWLIST=api.pixelstarships.com\n"
        "API_FLOW_CAPTURE_PATH_ALLOWLIST=/BattleService/GetBattle3\n",
        encoding="utf-8",
    )

    # CSV ya no se parsea: falla el JSON decode y pydantic-settings lanza SettingsError.
    with pytest.raises(SettingsError):
        Settings()


def test_settings_single_value_no_brackets_raises_error(
    tmp_path: Path, monkeypatch
) -> None:
    """A single bare value for a list field raises SettingsError (issue #16 fix)."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("API_FLOW_IGNORE_HOSTS", raising=False)
    monkeypatch.delenv("API_FLOW_CAPTURE_HOST_ALLOWLIST", raising=False)
    monkeypatch.delenv("API_FLOW_CAPTURE_PATH_ALLOWLIST", raising=False)
    monkeypatch.chdir(tmp_path)

    (tmp_path / ".env").write_text(
        "DATABASE_URL=sqlite:///./custom.db\n"
        "API_FLOW_IGNORE_HOSTS=api.pixelstarships.com\n"
        "API_FLOW_CAPTURE_HOST_ALLOWLIST=api.pixelstarships.com\n"
        "API_FLOW_CAPTURE_PATH_ALLOWLIST=/BattleService/GetBattle3\n",
        encoding="utf-8",
    )

    # Un valor sin brackets JSON ya no se acepta para un campo List.
    with pytest.raises(SettingsError):
        Settings()


def test_settings_empty_string_list_field_raises_settings_error(
    tmp_path: Path, monkeypatch, caplog
) -> None:
    """Empty-value contract (issue #16): `FIELD=` is invalid; use `FIELD=[]`.

    Deliberate break documented by this PR: a bare empty value no longer
    yields an empty list. `API_FLOW_IGNORE_HOSTS=[]` is the required spelling.
    The structured `event=config_invalid` ERROR log fires before the raise.
    """
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("API_FLOW_IGNORE_HOSTS", raising=False)
    monkeypatch.delenv("API_FLOW_CAPTURE_HOST_ALLOWLIST", raising=False)
    monkeypatch.delenv("API_FLOW_CAPTURE_PATH_ALLOWLIST", raising=False)
    monkeypatch.chdir(tmp_path)

    (tmp_path / ".env").write_text(
        "API_FLOW_IGNORE_HOSTS=\n",
        encoding="utf-8",
    )

    with caplog.at_level(logging.ERROR, logger="app.core.config"):
        with pytest.raises(SettingsError):
            Settings()

    error_records = [
        r for r in caplog.records
        if r.levelno == logging.ERROR and "field=API_FLOW_IGNORE_HOSTS" in r.getMessage()
    ]
    assert error_records, "expected a structured event=config_invalid ERROR record"
