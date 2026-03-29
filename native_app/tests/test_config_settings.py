from __future__ import annotations

from pathlib import Path

from app.core.config import Settings


def test_settings_loads_from_env_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("API_FLOW_IGNORE_HOSTS", raising=False)
    monkeypatch.delenv("API_FLOW_CAPTURE_HOST_ALLOWLIST", raising=False)
    monkeypatch.delenv("API_FLOW_CAPTURE_PATH_ALLOWLIST", raising=False)
    monkeypatch.chdir(tmp_path)

    (tmp_path / ".env").write_text(
        "DATABASE_URL=sqlite:///./custom.db\n"
        "API_FLOW_IGNORE_HOSTS=one.test,two.test\n"
        "API_FLOW_CAPTURE_HOST_ALLOWLIST=api.pixelstarships.com\n"
        "API_FLOW_CAPTURE_PATH_ALLOWLIST=/BattleService/GetBattle3,/BattleService/GetBattle3/\n",
        encoding="utf-8",
    )

    loaded = Settings()

    assert loaded.DATABASE_URL == "sqlite:///./custom.db"
    assert loaded.API_FLOW_IGNORE_HOSTS == ["one.test", "two.test"]
    assert loaded.API_FLOW_CAPTURE_HOST_ALLOWLIST == ["api.pixelstarships.com"]
    assert loaded.API_FLOW_CAPTURE_PATH_ALLOWLIST == ["/BattleService/GetBattle3", "/BattleService/GetBattle3/"]


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
