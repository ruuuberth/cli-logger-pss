from __future__ import annotations

import json
from datetime import datetime, timezone
from urllib.parse import urlsplit

from mitmproxy import ctx, http, tls

_EVENT_PREFIX = "API_FLOW_EVENT "


def _safe_text(payload: bytes | str | None) -> str:
    if payload is None:
        return ""
    if isinstance(payload, bytes):
        return payload.decode("utf-8", errors="replace")
    return str(payload)


def _truncate(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    return value[:max_chars] + "..."


def _extract_query(flow: http.HTTPFlow) -> str:
    try:
        query_value = flow.request.query
        if query_value:
            return str(query_value)
    except Exception:
        pass

    try:
        return urlsplit(flow.request.pretty_url).query
    except Exception:
        return ""


def _split_csv(value: str | None) -> list[str]:
    raw = str(value or "").strip()
    if not raw:
        return []
    return [token.strip() for token in raw.split(",") if token.strip()]


def _normalize_path(value: str) -> str:
    path = (value or "").strip()
    if not path:
        return "/"
    if not path.startswith("/"):
        path = "/" + path
    if len(path) > 1:
        path = path.rstrip("/")
    return path


class ApiFlowAddon:
    def load(self, loader):
        loader.add_option("api_flow_session_id", str, "unknown", "Session id from host app")
        loader.add_option("api_flow_body_max_chars", int, 4000, "Max body chars per event")
        loader.add_option(
            "api_flow_ignore_hosts",
            str,
            "",
            "Comma-separated host list for TLS passthrough",
        )
        loader.add_option(
            "api_flow_capture_hosts",
            str,
            "",
            "Comma-separated host allowlist for captured events",
        )
        loader.add_option(
            "api_flow_capture_paths",
            str,
            "",
            "Comma-separated path allowlist for captured events",
        )

    def tls_clienthello(self, data: tls.ClientHelloData) -> None:
        sni = (data.client_hello.sni or "").strip().lower()
        if not sni:
            return
        if self._is_ignored_host(sni):
            data.ignore_connection = True

    def _is_ignored_host(self, host: str) -> bool:
        raw_hosts = str(ctx.options.api_flow_ignore_hosts or "")
        configured = [token.strip().lower() for token in raw_hosts.split(",") if token.strip()]
        if not configured:
            return False
        for configured_host in configured:
            base = configured_host.lstrip(".")
            if host == base or host.endswith("." + base):
                return True
        return False

    def _should_capture_flow(self, flow: http.HTTPFlow) -> bool:
        host_allowlist = {token.lower() for token in _split_csv(getattr(ctx.options, "api_flow_capture_hosts", ""))}
        path_allowlist = {
            _normalize_path(token) for token in _split_csv(getattr(ctx.options, "api_flow_capture_paths", ""))
        }

        if host_allowlist:
            request_host = (flow.request.host or "").strip().lower()
            if request_host not in host_allowlist:
                return False

        if path_allowlist:
            request_path = _normalize_path((flow.request.path or "").split("?", 1)[0])
            if request_path not in path_allowlist:
                return False

        return True

    def response(self, flow: http.HTTPFlow) -> None:
        if not self._should_capture_flow(flow):
            return

        now = datetime.now(timezone.utc)
        max_chars = int(ctx.options.api_flow_body_max_chars)

        request_text = _truncate(_safe_text(flow.request.get_text(strict=False)), max_chars)
        response_text = _safe_text(flow.response.get_text(strict=False))
        request_headers = {str(k): str(v) for k, v in flow.request.headers.items(multi=True)}
        response_headers = {str(k): str(v) for k, v in flow.response.headers.items(multi=True)}

        duration_ms = None
        if flow.request.timestamp_start and flow.response.timestamp_end:
            duration_ms = int((flow.response.timestamp_end - flow.request.timestamp_start) * 1000)

        payload = {
            "session_id": str(ctx.options.api_flow_session_id),
            "captured_at": now.isoformat(),
            "direction": "response",
            "method": flow.request.method,
            "scheme": flow.request.scheme,
            "host": flow.request.host,
            "port": flow.request.port,
            "path": flow.request.path,
            "query": _extract_query(flow),
            "url_full": flow.request.pretty_url,
            "status_code": flow.response.status_code,
            "duration_ms": duration_ms,
            "request_headers_json": request_headers,
            "response_headers_json": response_headers,
            "request_body_preview": request_text,
            "response_body_preview": response_text,
            "request_size_bytes": len(flow.request.raw_content or b""),
            "response_size_bytes": len(flow.response.raw_content or b""),
            "content_type_request": flow.request.headers.get("content-type", ""),
            "content_type_response": flow.response.headers.get("content-type", ""),
            "tls": flow.request.scheme.lower() == "https",
            "error_text": None,
            "game_process_hint": "Pixel Starships",
            "flow_hash": flow.id,
        }
        print(_EVENT_PREFIX + json.dumps(payload, ensure_ascii=True), flush=True)

    def error(self, flow: http.HTTPFlow) -> None:
        if not self._should_capture_flow(flow):
            return

        now = datetime.now(timezone.utc)
        max_chars = int(ctx.options.api_flow_body_max_chars)
        payload = {
            "session_id": str(ctx.options.api_flow_session_id),
            "captured_at": now.isoformat(),
            "direction": "request",
            "method": flow.request.method,
            "scheme": flow.request.scheme,
            "host": flow.request.host,
            "port": flow.request.port,
            "path": flow.request.path,
            "query": _extract_query(flow),
            "url_full": flow.request.pretty_url,
            "status_code": None,
            "duration_ms": None,
            "request_headers_json": {str(k): str(v) for k, v in flow.request.headers.items(multi=True)},
            "response_headers_json": {},
            "request_body_preview": _truncate(_safe_text(flow.request.get_text(strict=False)), max_chars),
            "response_body_preview": "",
            "request_size_bytes": len(flow.request.raw_content or b""),
            "response_size_bytes": 0,
            "content_type_request": flow.request.headers.get("content-type", ""),
            "content_type_response": "",
            "tls": flow.request.scheme.lower() == "https",
            "error_text": str(flow.error) if flow.error else "request error",
            "game_process_hint": "Pixel Starships",
            "flow_hash": flow.id,
        }
        print(_EVENT_PREFIX + json.dumps(payload, ensure_ascii=True), flush=True)


addons = [ApiFlowAddon()]
