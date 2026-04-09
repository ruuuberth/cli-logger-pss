from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

pytest.importorskip("mitmproxy")

from app.services import mitm_api_flow_addon as addon


class _Headers(dict):
    def items(self, multi: bool = False):
        return super().items()


class _Message:
    def __init__(self, *, text: str, headers: dict[str, str], raw_content: bytes, status_code: int | None = None):
        self._text = text
        self.headers = _Headers(headers)
        self.raw_content = raw_content
        if status_code is not None:
            self.status_code = status_code

    def get_text(self, strict: bool = False) -> str:
        return self._text


class _Request(_Message):
    def __init__(
        self,
        *,
        text: str,
        method: str = "GET",
        scheme: str = "https",
        host: str = "api.pixelstarships.com",
        port: int = 443,
        path: str = "/BattleService/GetBattle3?battleId=1",
        pretty_url: str = "https://api.pixelstarships.com/BattleService/GetBattle3?battleId=1",
        headers: dict[str, str] | None = None,
        raw_content: bytes = b"request",
    ):
        super().__init__(text=text, headers=headers or {"content-type": "application/json"}, raw_content=raw_content)
        self.method = method
        self.scheme = scheme
        self.host = host
        self.port = port
        self.path = path
        self.pretty_url = pretty_url
        self.query = "a=1"
        self.timestamp_start = 1.0


class _Response(_Message):
    def __init__(self, *, text: str, status_code: int = 200, headers: dict[str, str] | None = None, raw_content: bytes = b"response"):
        super().__init__(
            text=text,
            headers=headers or {"content-type": "application/json"},
            raw_content=raw_content,
            status_code=status_code,
        )
        self.timestamp_end = 2.0


class _Flow:
    def __init__(
        self,
        *,
        req_text: str,
        res_text: str,
        error: str | None = None,
        host: str = "api.pixelstarships.com",
        path: str = "/BattleService/GetBattle3?battleId=1",
    ):
        self.request = _Request(
            text=req_text,
            host=host,
            path=path,
            pretty_url=f"https://{host}{path}",
        )
        self.response = _Response(text=res_text)
        self.error = error
        self.id = "flow-1"


def _capture_payload(monkeypatch: pytest.MonkeyPatch) -> dict:
    out: list[str] = []
    monkeypatch.setattr("builtins.print", lambda line, flush=True: out.append(line))
    return out


def _set_options(
    monkeypatch: pytest.MonkeyPatch,
    *,
    body_max_chars: int,
    capture_hosts: str = "api.pixelstarships.com",
    capture_paths: str = "/BattleService/GetBattle3",
) -> None:
    monkeypatch.setattr(
        addon,
        "ctx",
        SimpleNamespace(
            options=SimpleNamespace(
                api_flow_session_id="session-1",
                api_flow_body_max_chars=body_max_chars,
                api_flow_ignore_hosts="",
                api_flow_capture_hosts=capture_hosts,
                api_flow_capture_paths=capture_paths,
            )
        ),
    )


def test_error_truncates_request_body(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_options(monkeypatch, body_max_chars=5)
    out = _capture_payload(monkeypatch)

    flow = _Flow(req_text="abcdefghij", res_text="ok", error="boom")
    addon.ApiFlowAddon().error(flow)

    assert len(out) == 1
    payload = json.loads(out[0][len("API_FLOW_EVENT ") :])
    assert payload["request_body_preview"] == "abcde..."


def test_response_and_error_emit_expected_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_options(monkeypatch, body_max_chars=100)
    out = _capture_payload(monkeypatch)

    flow = _Flow(req_text="req", res_text="res", error="network")
    api_addon = addon.ApiFlowAddon()
    api_addon.response(flow)
    api_addon.error(flow)

    assert len(out) == 2
    response_payload = json.loads(out[0][len("API_FLOW_EVENT ") :])
    error_payload = json.loads(out[1][len("API_FLOW_EVENT ") :])

    assert response_payload["direction"] == "response"
    assert response_payload["status_code"] == 200
    assert response_payload["flow_hash"] == "flow-1"

    assert error_payload["direction"] == "request"
    assert error_payload["status_code"] is None
    assert error_payload["error_text"] == "network"
    assert error_payload["flow_hash"] == "flow-1"


def test_drops_event_when_host_not_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_options(monkeypatch, body_max_chars=100)
    out = _capture_payload(monkeypatch)

    flow = _Flow(req_text="req", res_text="res", host="other.host")
    addon.ApiFlowAddon().response(flow)

    assert out == []


def test_drops_event_when_path_not_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_options(monkeypatch, body_max_chars=100)
    out = _capture_payload(monkeypatch)

    flow = _Flow(req_text="req", res_text="res", path="/BattleService/FinaliseBattle15")
    addon.ApiFlowAddon().response(flow)

    assert out == []


def test_allows_path_with_querystring(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_options(monkeypatch, body_max_chars=100)
    out = _capture_payload(monkeypatch)

    flow = _Flow(req_text="req", res_text="res", path="/BattleService/GetBattle3?battleId=121")
    addon.ApiFlowAddon().response(flow)

    assert len(out) == 1


def test_response_body_is_not_truncated(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_options(monkeypatch, body_max_chars=5)
    out = _capture_payload(monkeypatch)

    long_response = "z" * 200
    flow = _Flow(req_text="req", res_text=long_response, path="/BattleService/GetBattle3?battleId=999")
    addon.ApiFlowAddon().response(flow)

    assert len(out) == 1
    payload = json.loads(out[0][len("API_FLOW_EVENT ") :])
    assert payload["response_body_preview"] == long_response


def test_captures_all_when_allowlists_are_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_options(monkeypatch, body_max_chars=100, capture_hosts="", capture_paths="")
    out = _capture_payload(monkeypatch)

    flow = _Flow(req_text="req", res_text="res", host="other.host", path="/Some/OtherEndpoint")
    addon.ApiFlowAddon().response(flow)

    assert len(out) == 1


def test_tls_clienthello_ignores_configured_hosts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        addon,
        "ctx",
        SimpleNamespace(
            options=SimpleNamespace(
                api_flow_ignore_hosts="perf-events.cloud.unity3d.com",
                api_flow_session_id="session-1",
                api_flow_body_max_chars=100,
                api_flow_capture_hosts="",
                api_flow_capture_paths="",
            )
        ),
    )

    data = SimpleNamespace(
        client_hello=SimpleNamespace(sni="perf-events.cloud.unity3d.com"),
        ignore_connection=False,
    )

    addon.ApiFlowAddon().tls_clienthello(data)
    assert data.ignore_connection is True
