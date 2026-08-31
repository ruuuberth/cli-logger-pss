from __future__ import annotations

import hashlib
import os
import logging
import sys
import pytest
from pathlib import Path
from types import SimpleNamespace

from app.services.api_flow_capture import ApiFlowCaptureManager


class _DummyProcess:
    def __init__(self) -> None:
        self.stdout = []
        self.pid = 123

    def poll(self):
        return None

    def terminate(self) -> None:
        pass

    def wait(self, timeout: int = 0) -> None:
        pass

    def kill(self) -> None:
        pass


class _DummyThread:
    def __init__(self, target, daemon: bool = False) -> None:
        self.target = target
        self.daemon = daemon

    def start(self) -> None:
        return


def _addon_bytes() -> bytes:
    return (Path(__file__).resolve().parents[1] / "app/services/mitm_api_flow_addon.py").read_bytes()


def _mock_mitmproxy_binary_resolution(monkeypatch) -> None:
    monkeypatch.setattr("app.services.api_flow_capture.shutil.which", lambda _cmd: "/usr/bin/mitmdump")
    monkeypatch.delenv("MITMPROXY_BINARY", raising=False)
    # Simulate NO venv: sys.prefix == sys.base_prefix
    monkeypatch.setattr("sys.prefix", "/usr", raising=False)
    monkeypatch.setattr("sys.base_prefix", "/usr", raising=False)


def test_start_capture_passes_allowlist_options(monkeypatch) -> None:
    manager = ApiFlowCaptureManager()
    _mock_mitmproxy_binary_resolution(monkeypatch)

    monkeypatch.setattr("app.services.api_flow_capture.threading.Thread", _DummyThread)

    captured_cmd = {}

    def _fake_popen(cmd, stdout=None, stderr=None, text=None, bufsize=None):
        captured_cmd["cmd"] = list(cmd)
        return _DummyProcess()

    monkeypatch.setattr("app.services.api_flow_capture.subprocess.Popen", _fake_popen)

    monkeypatch.setattr("app.services.api_flow_capture.settings", SimpleNamespace(
        API_FLOW_ENABLED=True,
        MITMPROXY_BINARY="mitmdump",
        MITMPROXY_LISTEN_HOST="127.0.0.1",
        MITMPROXY_LISTEN_PORT=8081,
        API_FLOW_BODY_MAX_CHARS=4000,
        API_FLOW_IGNORE_HOSTS=[],
        API_FLOW_CAPTURE_HOST_ALLOWLIST=["api.pixelstarships.com"],
        API_FLOW_CAPTURE_PATH_ALLOWLIST=["/BattleService/GetBattle3"],
    ))

    session = manager.start_capture()

    assert session.pid == 123
    cmd = captured_cmd["cmd"]
    assert "--set" in cmd
    assert "api_flow_capture_hosts=api.pixelstarships.com" in cmd
    assert "api_flow_capture_paths=/BattleService/GetBattle3" in cmd


def test_start_capture_uses_source_addon_when_file_exists(monkeypatch, tmp_path: Path) -> None:
    manager = ApiFlowCaptureManager()
    _mock_mitmproxy_binary_resolution(monkeypatch)
    monkeypatch.setattr("app.services.api_flow_capture.threading.Thread", _DummyThread)
    monkeypatch.setattr("app.services.api_flow_capture.Path.exists", lambda _self: True)

    captured_cmd = {}

    def _fake_popen(cmd, stdout=None, stderr=None, text=None, bufsize=None):
        captured_cmd["cmd"] = list(cmd)
        return _DummyProcess()

    monkeypatch.setattr("app.services.api_flow_capture.subprocess.Popen", _fake_popen)
    monkeypatch.setattr("app.services.api_flow_capture.settings", SimpleNamespace(
        API_FLOW_ENABLED=True,
        MITMPROXY_BINARY="mitmdump",
        MITMPROXY_LISTEN_HOST="127.0.0.1",
        MITMPROXY_LISTEN_PORT=8081,
        API_FLOW_BODY_MAX_CHARS=4000,
        API_FLOW_IGNORE_HOSTS=[],
        API_FLOW_CAPTURE_HOST_ALLOWLIST=["api.pixelstarships.com"],
        API_FLOW_CAPTURE_PATH_ALLOWLIST=["/BattleService/GetBattle3"],
    ))

    manager.start_capture()

    cmd = captured_cmd["cmd"]
    addon_idx = cmd.index("-s") + 1
    assert cmd[addon_idx].endswith("mitm_api_flow_addon.py")
    assert manager._temp_addon_path is None


def test_start_capture_in_frozen_mode_uses_temp_addon(monkeypatch, tmp_path: Path) -> None:
    manager = ApiFlowCaptureManager()
    _mock_mitmproxy_binary_resolution(monkeypatch)
    monkeypatch.setattr("app.services.api_flow_capture.threading.Thread", _DummyThread)
    monkeypatch.setattr("app.services.api_flow_capture.tempfile.gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr("app.services.api_flow_capture.sys.frozen", True, raising=False)

    captured_cmd = {}

    def _fake_popen(cmd, stdout=None, stderr=None, text=None, bufsize=None):
        captured_cmd["cmd"] = list(cmd)
        return _DummyProcess()

    monkeypatch.setattr("app.services.api_flow_capture.subprocess.Popen", _fake_popen)
    monkeypatch.setattr("app.services.api_flow_capture.settings", SimpleNamespace(
        API_FLOW_ENABLED=True,
        MITMPROXY_BINARY="mitmdump",
        MITMPROXY_LISTEN_HOST="127.0.0.1",
        MITMPROXY_LISTEN_PORT=8081,
        API_FLOW_BODY_MAX_CHARS=4000,
        API_FLOW_IGNORE_HOSTS=[],
        API_FLOW_CAPTURE_HOST_ALLOWLIST=["api.pixelstarships.com"],
        API_FLOW_CAPTURE_PATH_ALLOWLIST=["/BattleService/GetBattle3"],
    ))

    manager.start_capture()
    cmd = captured_cmd["cmd"]
    addon_idx = cmd.index("-s") + 1
    addon_path = Path(cmd[addon_idx])
    assert addon_path.exists()
    assert "pss_logger_addons" in str(addon_path)
    assert manager._temp_addon_path == addon_path


def test_start_capture_logs_resolved_addon_and_binary(monkeypatch, caplog) -> None:
    manager = ApiFlowCaptureManager()
    _mock_mitmproxy_binary_resolution(monkeypatch)
    monkeypatch.setattr("app.services.api_flow_capture.threading.Thread", _DummyThread)

    captured_cmd = {}

    def _fake_popen(cmd, stdout=None, stderr=None, text=None, bufsize=None):
        captured_cmd["cmd"] = list(cmd)
        return _DummyProcess()

    monkeypatch.setattr("app.services.api_flow_capture.subprocess.Popen", _fake_popen)
    monkeypatch.setattr("app.services.api_flow_capture.settings", SimpleNamespace(
        API_FLOW_ENABLED=True,
        MITMPROXY_BINARY="mitmdump",
        MITMPROXY_LISTEN_HOST="127.0.0.1",
        MITMPROXY_LISTEN_PORT=8081,
        API_FLOW_BODY_MAX_CHARS=4000,
        API_FLOW_IGNORE_HOSTS=[],
        API_FLOW_CAPTURE_HOST_ALLOWLIST=["api.pixelstarships.com"],
        API_FLOW_CAPTURE_PATH_ALLOWLIST=["/BattleService/GetBattle3"],
    ))

    with caplog.at_level(logging.INFO):
        manager.start_capture()

    assert "event=capture_addon_resolved" in caplog.text
    assert "mitmproxy_binary=" in caplog.text


def test_start_capture_fallbacks_to_temp_addon_when_source_missing(monkeypatch, tmp_path: Path) -> None:
    manager = ApiFlowCaptureManager()
    _mock_mitmproxy_binary_resolution(monkeypatch)
    monkeypatch.setattr("app.services.api_flow_capture.threading.Thread", _DummyThread)
    original_exists = Path.exists

    def _exists(self: Path) -> bool:
        if str(self).endswith("mitm_api_flow_addon.py"):
            return False
        return original_exists(self)

    monkeypatch.setattr("app.services.api_flow_capture.Path.exists", _exists)
    monkeypatch.setattr("app.services.api_flow_capture.pkgutil.get_data", lambda *_args, **_kwargs: _addon_bytes())
    monkeypatch.setattr("app.services.api_flow_capture.tempfile.gettempdir", lambda: str(tmp_path))

    captured_cmd = {}

    def _fake_popen(cmd, stdout=None, stderr=None, text=None, bufsize=None):
        captured_cmd["cmd"] = list(cmd)
        return _DummyProcess()

    monkeypatch.setattr("app.services.api_flow_capture.subprocess.Popen", _fake_popen)
    monkeypatch.setattr("app.services.api_flow_capture.settings", SimpleNamespace(
        API_FLOW_ENABLED=True,
        MITMPROXY_BINARY="mitmdump",
        MITMPROXY_LISTEN_HOST="127.0.0.1",
        MITMPROXY_LISTEN_PORT=8081,
        API_FLOW_BODY_MAX_CHARS=4000,
        API_FLOW_IGNORE_HOSTS=[],
        API_FLOW_CAPTURE_HOST_ALLOWLIST=["api.pixelstarships.com"],
        API_FLOW_CAPTURE_PATH_ALLOWLIST=["/BattleService/GetBattle3"],
    ))

    manager.start_capture()

    cmd = captured_cmd["cmd"]
    addon_idx = cmd.index("-s") + 1
    addon_path = Path(cmd[addon_idx])
    assert addon_path.exists()
    assert manager._temp_addon_path == addon_path


def test_start_capture_rejects_mei_addon_path(monkeypatch) -> None:
    manager = ApiFlowCaptureManager()
    monkeypatch.setattr(manager, "_resolve_addon_path", lambda: Path("/tmp/_MEI123/app/services/mitm_api_flow_addon.py"))
    monkeypatch.setattr(manager, "_resolve_mitmproxy_binary_path", lambda: "mitmdump")
    monkeypatch.setattr("app.services.api_flow_capture.sys.frozen", True, raising=False)
    monkeypatch.setattr("app.services.api_flow_capture.settings", SimpleNamespace(
        API_FLOW_ENABLED=True,
        MITMPROXY_BINARY="mitmdump",
        MITMPROXY_LISTEN_HOST="127.0.0.1",
        MITMPROXY_LISTEN_PORT=8081,
        API_FLOW_BODY_MAX_CHARS=4000,
        API_FLOW_IGNORE_HOSTS=[],
        API_FLOW_CAPTURE_HOST_ALLOWLIST=["api.pixelstarships.com"],
        API_FLOW_CAPTURE_PATH_ALLOWLIST=["/BattleService/GetBattle3"],
    ))

    try:
        manager.start_capture()
    except RuntimeError as exc:
        assert "_MEI internal bundle" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for _MEI addon path")


def test_start_capture_fails_on_sha_mismatch(monkeypatch) -> None:
    manager = ApiFlowCaptureManager()
    _mock_mitmproxy_binary_resolution(monkeypatch)
    monkeypatch.setattr("app.services.api_flow_capture.Path.exists", lambda _self: False)
    monkeypatch.setattr("app.services.api_flow_capture.pkgutil.get_data", lambda *_args, **_kwargs: b"tampered")
    monkeypatch.setattr("app.services.api_flow_capture.settings", SimpleNamespace(
        API_FLOW_ENABLED=True,
        MITMPROXY_BINARY="mitmdump",
        MITMPROXY_LISTEN_HOST="127.0.0.1",
        MITMPROXY_LISTEN_PORT=8081,
        API_FLOW_BODY_MAX_CHARS=4000,
        API_FLOW_IGNORE_HOSTS=[],
        API_FLOW_CAPTURE_HOST_ALLOWLIST=["api.pixelstarships.com"],
        API_FLOW_CAPTURE_PATH_ALLOWLIST=["/BattleService/GetBattle3"],
    ))

    try:
        manager.start_capture()
    except RuntimeError as exc:
        assert "SHA256 mismatch" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for addon SHA mismatch.")


def test_validate_addon_integrity_accepts_expected_hash() -> None:
    manager = ApiFlowCaptureManager()
    addon_bytes = _addon_bytes()
    digest = hashlib.sha256(manager._normalize_addon_bytes(addon_bytes)).hexdigest()
    assert digest
    manager._validate_addon_integrity(addon_bytes)


def test_validate_addon_integrity_accepts_crlf_variant() -> None:
    manager = ApiFlowCaptureManager()
    addon_bytes = _addon_bytes()
    crlf_bytes = addon_bytes.replace(b"\n", b"\r\n")
    manager._validate_addon_integrity(crlf_bytes)


def test_temp_addon_is_cleaned_on_stop_capture(monkeypatch, tmp_path: Path) -> None:
    manager = ApiFlowCaptureManager()
    path = tmp_path / "addon_temp.py"
    path.write_text("print('addon')", encoding="utf-8")
    manager._temp_addon_path = path
    manager._process = _DummyProcess()

    manager.stop_capture()

    assert not path.exists()
    assert manager._temp_addon_path is None


def test_temp_addon_is_cleaned_when_reader_finishes(monkeypatch, tmp_path: Path) -> None:
    manager = ApiFlowCaptureManager()
    path = tmp_path / "addon_temp.py"
    path.write_text("print('addon')", encoding="utf-8")
    manager._temp_addon_path = path

    class _ProcessWithStdout:
        def __init__(self) -> None:
            self.stdout = []

        def poll(self):
            return 0

    manager._process = _ProcessWithStdout()
    manager._read_stdout()

    assert not path.exists()
    assert manager._temp_addon_path is None


def test_start_capture_raises_clear_error_when_no_addon_source(monkeypatch) -> None:
    manager = ApiFlowCaptureManager()
    _mock_mitmproxy_binary_resolution(monkeypatch)
    monkeypatch.setattr("app.services.api_flow_capture.Path.exists", lambda _self: False)
    monkeypatch.setattr("app.services.api_flow_capture.pkgutil.get_data", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("app.services.api_flow_capture.settings", SimpleNamespace(
        API_FLOW_ENABLED=True,
        MITMPROXY_BINARY="mitmdump",
        MITMPROXY_LISTEN_HOST="127.0.0.1",
        MITMPROXY_LISTEN_PORT=8081,
        API_FLOW_BODY_MAX_CHARS=4000,
        API_FLOW_IGNORE_HOSTS=[],
        API_FLOW_CAPTURE_HOST_ALLOWLIST=["api.pixelstarships.com"],
        API_FLOW_CAPTURE_PATH_ALLOWLIST=["/BattleService/GetBattle3"],
    ))

    try:
        manager.start_capture()
    except RuntimeError as exc:
        assert "capture_addon_unresolvable" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for missing addon source.")


def test_resolve_mitmproxy_binary_from_env_override(monkeypatch, tmp_path: Path) -> None:
    manager = ApiFlowCaptureManager()
    fake_binary = tmp_path / "mitmdump-custom"
    fake_binary.write_text("#!/bin/sh\n", encoding="utf-8")
    os.chmod(fake_binary, 0o755)

    monkeypatch.setenv("MITMPROXY_BINARY", str(fake_binary))
    monkeypatch.setattr("app.services.api_flow_capture.settings", SimpleNamespace(
        MITMPROXY_BINARY=str(fake_binary),
    ))

    resolved = manager._resolve_mitmproxy_binary_path()
    assert str(resolved) == str(fake_binary)


def test_resolve_mitmproxy_binary_from_packaged_path(monkeypatch, tmp_path: Path) -> None:
    manager = ApiFlowCaptureManager()
    packaged_binary = tmp_path / "third_party" / "mitmproxy" / "mitmdump"
    packaged_binary.parent.mkdir(parents=True, exist_ok=True)
    packaged_binary.write_text("#!/bin/sh\n", encoding="utf-8")
    os.chmod(packaged_binary, 0o755)

    # Simulate NO venv: sys.prefix == sys.base_prefix
    monkeypatch.setattr("sys.prefix", str(tmp_path / "base"), raising=False)
    monkeypatch.setattr("sys.base_prefix", str(tmp_path / "base"), raising=False)

    monkeypatch.delenv("MITMPROXY_BINARY", raising=False)
    monkeypatch.setattr(manager, "_resolve_packaged_mitmproxy_path", lambda: packaged_binary)
    monkeypatch.setattr("app.services.api_flow_capture.shutil.which", lambda _cmd: None)
    monkeypatch.setattr("app.services.api_flow_capture.settings", SimpleNamespace(MITMPROXY_BINARY="mitmdump"))

    resolved = manager._resolve_mitmproxy_binary_path()
    assert resolved == packaged_binary


def test_resolve_mitmproxy_binary_from_path_fallback(monkeypatch) -> None:
    manager = ApiFlowCaptureManager()
    
    # Simulate NO venv: sys.prefix == sys.base_prefix
    monkeypatch.setattr("sys.prefix", "/usr", raising=False)
    monkeypatch.setattr("sys.base_prefix", "/usr", raising=False)

    monkeypatch.delenv("MITMPROXY_BINARY", raising=False)
    monkeypatch.setattr(manager, "_resolve_packaged_mitmproxy_path", lambda: None)
    monkeypatch.setattr("app.services.api_flow_capture.shutil.which", lambda _cmd: "/usr/bin/mitmdump")
    monkeypatch.setattr("app.services.api_flow_capture.settings", SimpleNamespace(MITMPROXY_BINARY="mitmdump"))

    resolved = manager._resolve_mitmproxy_binary_path()
    assert resolved == "mitmdump"


def test_start_capture_fails_with_capture_proxy_missing_when_none_available(monkeypatch) -> None:
    manager = ApiFlowCaptureManager()
    
    # Simulate NO venv: sys.prefix == sys.base_prefix
    monkeypatch.setattr("sys.prefix", "/usr", raising=False)
    monkeypatch.setattr("sys.base_prefix", "/usr", raising=False)
    
    monkeypatch.delenv("MITMPROXY_BINARY", raising=False)
    monkeypatch.setattr(manager, "_resolve_packaged_mitmproxy_path", lambda: None)
    monkeypatch.setattr("app.services.api_flow_capture.shutil.which", lambda _cmd: None)
    monkeypatch.setattr("app.services.api_flow_capture.settings", SimpleNamespace(MITMPROXY_BINARY="mitmdump"))

    try:
        manager._resolve_mitmproxy_binary_path()
    except RuntimeError as exc:
        assert "capture_proxy_missing" in str(exc)
    else:
        raise AssertionError("Expected missing proxy diagnostic error")


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific venv path test")
def test_resolve_mitmproxy_binary_from_active_venv(monkeypatch, tmp_path: Path) -> None:
    """Test that detects mitmdump in the active venv."""
    manager = ApiFlowCaptureManager()

    # Simulate venv active: sys.prefix != sys.base_prefix
    venv_root = tmp_path / "venv"
    base_root = tmp_path / "base"
    venv_root.mkdir(parents=True)
    base_root.mkdir(parents=True)

    monkeypatch.setattr("sys.prefix", str(venv_root), raising=False)
    monkeypatch.setattr("sys.base_prefix", str(base_root), raising=False)

    # Create mitmdump in venv/Scripts
    venv_binary = venv_root / "Scripts" / "mitmdump.exe"
    venv_binary.parent.mkdir(parents=True, exist_ok=True)
    venv_binary.write_text("@echo off\n", encoding="utf-8")

    monkeypatch.delenv("MITMPROXY_BINARY", raising=False)
    monkeypatch.setattr(manager, "_resolve_packaged_mitmproxy_path", lambda: None)
    monkeypatch.setattr("app.services.api_flow_capture.shutil.which", lambda _cmd: None)
    monkeypatch.setattr("app.services.api_flow_capture.settings", SimpleNamespace(MITMPROXY_BINARY="mitmdump"))

    resolved = manager._resolve_mitmproxy_binary_path()
    assert resolved == venv_binary


def test_resolve_mitmproxy_binary_venv_not_active_falls_back(monkeypatch, tmp_path: Path) -> None:
    """Test that does NOT use venv if sys.prefix == sys.base_prefix (no venv)."""
    manager = ApiFlowCaptureManager()

    # Simulate NO venv: sys.prefix == sys.base_prefix
    base_root = tmp_path / "base"
    base_root.mkdir(parents=True)
    monkeypatch.setattr("sys.prefix", str(base_root), raising=False)
    monkeypatch.setattr("sys.base_prefix", str(base_root), raising=False)

    # Create mitmdump in PATH (via shutil.which)
    monkeypatch.setattr("app.services.api_flow_capture.shutil.which", lambda _cmd: "/usr/bin/mitmdump")
    monkeypatch.delenv("MITMPROXY_BINARY", raising=False)
    monkeypatch.setattr(manager, "_resolve_packaged_mitmproxy_path", lambda: None)
    monkeypatch.setattr("app.services.api_flow_capture.settings", SimpleNamespace(MITMPROXY_BINARY="mitmdump"))

    resolved = manager._resolve_mitmproxy_binary_path()
    assert resolved == "mitmdump"  # Should fall back to PATH


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific venv path test")
def test_resolve_mitmproxy_binary_venv_priority_over_packaged(monkeypatch, tmp_path: Path) -> None:
    """Test that venv has priority over third_party/ packaged binary."""
    manager = ApiFlowCaptureManager()

    # Simulate venv active
    venv_root = tmp_path / "venv"
    base_root = tmp_path / "base"
    venv_root.mkdir(parents=True)
    base_root.mkdir(parents=True)

    monkeypatch.setattr("sys.prefix", str(venv_root), raising=False)
    monkeypatch.setattr("sys.base_prefix", str(base_root), raising=False)

    # Create mitmdump in venv/Scripts
    venv_binary = venv_root / "Scripts" / "mitmdump.exe"
    venv_binary.parent.mkdir(parents=True, exist_ok=True)
    venv_binary.write_text("@echo off\n", encoding="utf-8")

    # Also create a packaged binary (should be ignored due to lower priority)
    packaged_binary = tmp_path / "third_party" / "mitmproxy" / "mitmdump.exe"
    packaged_binary.parent.mkdir(parents=True, exist_ok=True)
    packaged_binary.write_text("@echo off\n", encoding="utf-8")

    monkeypatch.delenv("MITMPROXY_BINARY", raising=False)
    monkeypatch.setattr(manager, "_resolve_packaged_mitmproxy_path", lambda: packaged_binary)
    monkeypatch.setattr("app.services.api_flow_capture.shutil.which", lambda _cmd: None)
    monkeypatch.setattr("app.services.api_flow_capture.settings", SimpleNamespace(MITMPROXY_BINARY="mitmdump"))

    resolved = manager._resolve_mitmproxy_binary_path()
    assert resolved == venv_binary  # Venv should win over packaged
