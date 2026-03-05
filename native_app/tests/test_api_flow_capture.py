from __future__ import annotations

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
