from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError
from pydantic_settings import SettingsError

from app.core.config import Settings


def test_settings_loads_from_env_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("API_FLOW_IGNORE_HOSTS", raising=False)
    monkeypatch.delenv("API_FLOW_CAPTURE_HOST_ALLOWLIST", raising=False)
    monkeypatch.delenv("API_FLOW_CAPTURE_PATH_ALLOWLIST", raising=False)
    monkeypatch.chdir(tmp_path)

    (tmp_path / ".env").write_text(
        "DATABASE_URL=sqlite:///./custom.db\n"
        'API_FLOW_IGNORE_HOSTS=["one.test","two.test"]\n'
        'API_FLOW_CAPTURE_HOST_ALLOWLIST=["api.pixelstarships.com"]\n'
        "API_FLOW_CAPTURE_PATH_ALLOWLIST="
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


def test_settings_empty_json_array_list_field_returns_empty_list(
    tmp_path: Path, monkeypatch
) -> None:
    """Empty-value contract (issue #16): an empty list is spelled `FIELD=[]`."""
    monkeypatch.delenv("API_FLOW_IGNORE_HOSTS", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(
        "API_FLOW_IGNORE_HOSTS=[]\n",
        encoding="utf-8",
    )
    loaded = Settings()
    assert loaded.API_FLOW_IGNORE_HOSTS == []


def test_settings_allowed_hosts_env_json_override(monkeypatch, tmp_path: Path) -> None:
    """ALLOWED_HOSTS accepts only a JSON array from OS env vars (no CSV fallback)."""
    monkeypatch.delenv("ALLOWED_HOSTS", raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ALLOWED_HOSTS", '["https://example.com"]')
    loaded = Settings()
    assert loaded.ALLOWED_HOSTS == ["https://example.com"]


def test_settings_allowed_hosts_env_csv_raises_settings_error(
    monkeypatch, tmp_path: Path
) -> None:
    """A CSV value for ALLOWED_HOSTS via OS env var raises SettingsError (issue #16)."""
    monkeypatch.delenv("ALLOWED_HOSTS", raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ALLOWED_HOSTS", "https://example.com,https://other.com")
    with pytest.raises(SettingsError):
        Settings()


def test_settings_mitmproxy_mode_default_is_regular(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("MITMPROXY_MODE", raising=False)
    monkeypatch.chdir(tmp_path)
    loaded = Settings()
    assert loaded.MITMPROXY_MODE == "regular"


@pytest.mark.parametrize("raw", ["transparent", "regular"])
def test_settings_mitmproxy_mode_accepts_valid_values(
    monkeypatch, tmp_path: Path, raw: str
) -> None:
    """Closed contract (#48): exact match on mitmproxy's two used modes."""
    monkeypatch.setenv("MITMPROXY_MODE", raw)
    monkeypatch.chdir(tmp_path)
    loaded = Settings()
    assert loaded.MITMPROXY_MODE == raw


def test_settings_mitmproxy_mode_typo_raises(monkeypatch, tmp_path: Path) -> None:
    """A typo must fail loudly at startup, not silently kill capture later (#48)."""
    monkeypatch.setenv("MITMPROXY_MODE", "trasparent")
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValidationError, match="regular.*transparent"):
        Settings()


def test_settings_mitmproxy_mode_unsupported_mitm_mode_raises(
    monkeypatch, tmp_path: Path
) -> None:
    """socks5/upstream are not in the closed list — rejected, per issue #48 decision."""
    monkeypatch.setenv("MITMPROXY_MODE", "socks5")
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValidationError, match="MITMPROXY_MODE"):
        Settings()


def test_settings_default_capture_allowlists(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("API_FLOW_IGNORE_HOSTS", raising=False)
    monkeypatch.delenv("API_FLOW_CAPTURE_HOST_ALLOWLIST", raising=False)
    monkeypatch.delenv("API_FLOW_CAPTURE_PATH_ALLOWLIST", raising=False)
    loaded = Settings()
    assert loaded.API_FLOW_CAPTURE_HOST_ALLOWLIST == ["api.pixelstarships.com"]
    assert loaded.API_FLOW_CAPTURE_PATH_ALLOWLIST == ["/BattleService/GetBattle3"]
    assert "perf-events.cloud.unity3d.com" in loaded.API_FLOW_IGNORE_HOSTS
    assert "config.uca.cloud.unity3d.com" in loaded.API_FLOW_IGNORE_HOSTS
