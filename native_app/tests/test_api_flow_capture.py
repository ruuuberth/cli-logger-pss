from __future__ import annotations

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


def test_start_capture_passes_allowlist_options(monkeypatch) -> None:
    manager = ApiFlowCaptureManager()

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


def test_start_capture_fallbacks_to_temp_addon_when_source_missing(monkeypatch, tmp_path: Path) -> None:
    manager = ApiFlowCaptureManager()
    monkeypatch.setattr("app.services.api_flow_capture.threading.Thread", _DummyThread)
    original_exists = Path.exists

    def _exists(self: Path) -> bool:
        if str(self).endswith("mitm_api_flow_addon.py"):
            return False
        return original_exists(self)

    monkeypatch.setattr("app.services.api_flow_capture.Path.exists", _exists)
    monkeypatch.setattr("app.services.api_flow_capture.pkgutil.get_data", lambda *_args, **_kwargs: b"print('addon')")
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


def test_temp_addon_is_cleaned_on_stop_capture(monkeypatch, tmp_path: Path) -> None:
    manager = ApiFlowCaptureManager()
    path = tmp_path / "addon_temp.py"
    path.write_text("print('addon')", encoding="utf-8")
    manager._temp_addon_path = path
    manager._process = _DummyProcess()

    manager.stop_capture()

    assert not path.exists()
    assert manager._temp_addon_path is None


def test_start_capture_raises_clear_error_when_no_addon_source(monkeypatch) -> None:
    manager = ApiFlowCaptureManager()
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
        assert "No se pudo resolver el addon mitmproxy (source/frozen)." in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for missing addon source.")
