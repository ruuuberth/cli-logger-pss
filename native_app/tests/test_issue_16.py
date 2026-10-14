from __future__ import annotations

import logging
import pytest
from pathlib import Path

from app.core.config import Settings


def test_settings_json_arrays_work_with_dotenv(tmp_path: Path, monkeypatch) -> None:
    """JSON array format in .env should be parsed correctly (post-fix behavior)."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("API_FLOW_IGNORE_HOSTS", raising=False)
    monkeypatch.delenv("API_FLOW_CAPTURE_HOST_ALLOWLIST", raising=False)
    monkeypatch.delenv("API_FLOW_CAPTURE_PATH_ALLOWLIST", raising=False)
    monkeypatch.chdir(tmp_path)

    (tmp_path / ".env").write_text(
        "DATABASE_URL=sqlite:///./custom.db\n"
        'API_FLOW_IGNORE_HOSTS=["one.test","two.test"]\n'
        'API_FLOW_CAPTURE_HOST_ALLOWLIST=["api.pixelstarships.com"]\n'
        'API_FLOW_CAPTURE_PATH_ALLOWLIST=["/BattleService/GetBattle3","/BattleService/GetBattle3/"]\n',
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


def test_settings_csv_raises_validation_error(tmp_path: Path, monkeypatch, caplog) -> None:
    """CSV format in .env should no longer be silently parsed (issue #16 fix)."""
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

    with pytest.raises(Exception):  # pydantic ValidationError when CSV is used
        loaded = Settings()


def test_settings_single_value_no_brackets_raises_error(tmp_path: Path, monkeypatch, caplog) -> None:
    """A single value without JSON brackets should raise ValidationError after the fix (issue #16)."""
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

    with pytest.raises(Exception):  # pydantic ValidationError when raw string used for List field
        loaded = Settings()