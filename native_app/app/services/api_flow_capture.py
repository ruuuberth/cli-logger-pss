from __future__ import annotations

import json
import logging
import re
import subprocess
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from app.core.config import settings

logger = logging.getLogger(__name__)

_EVENT_PREFIX = "API_FLOW_EVENT "


@dataclass
class CaptureSession:
    session_id: str
    started_at: datetime
    listen_host: str
    listen_port: int
    pid: int | None


class ApiFlowCaptureManager:
    def __init__(self) -> None:
        self._process: subprocess.Popen[str] | None = None
        self._reader_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._event_callbacks: list[Callable[[dict[str, Any]], None]] = []
        self._status_callbacks: list[Callable[[str], None]] = []
        self._current_session: CaptureSession | None = None

    def subscribe(self, callback: Callable[[dict[str, Any]], None]) -> None:
        self._event_callbacks.append(callback)

    def subscribe_status(self, callback: Callable[[str], None]) -> None:
        self._status_callbacks.append(callback)

    def start_capture(self) -> CaptureSession:
        with self._lock:
            if self.is_running() and self._current_session is not None:
                return self._current_session

            if not settings.API_FLOW_ENABLED:
                raise RuntimeError("API Flow está deshabilitado por configuración (.env).")

            addon_path = Path(__file__).resolve().parent / "mitm_api_flow_addon.py"
            if not addon_path.exists():
                raise RuntimeError(f"No se encontró el addon de mitmproxy: {addon_path}")

            session_id = uuid4().hex
            cmd = [
                settings.MITMPROXY_BINARY,
                "-s",
                str(addon_path),
                "--listen-host",
                settings.MITMPROXY_LISTEN_HOST,
                "--listen-port",
                str(settings.MITMPROXY_LISTEN_PORT),
                "--set",
                f"api_flow_session_id={session_id}",
                "--set",
                f"api_flow_body_max_chars={settings.API_FLOW_BODY_MAX_CHARS}",
                "--set",
                f"api_flow_ignore_hosts={','.join(settings.API_FLOW_IGNORE_HOSTS)}",
                "--set",
                f"api_flow_capture_hosts={','.join(settings.API_FLOW_CAPTURE_HOST_ALLOWLIST)}",
                "--set",
                f"api_flow_capture_paths={','.join(settings.API_FLOW_CAPTURE_PATH_ALLOWLIST)}",
            ]
            ignore_regex = self._build_ignore_hosts_regex(settings.API_FLOW_IGNORE_HOSTS)
            if ignore_regex:
                cmd.extend(["--ignore-hosts", ignore_regex])

            self._stop_event.clear()
            try:
                self._process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
            except FileNotFoundError as exc:
                raise RuntimeError(
                    f"No se encontró el binario '{settings.MITMPROXY_BINARY}'. Instala mitmproxy o ajusta MITMPROXY_BINARY."
                ) from exc
            except Exception as exc:
                raise RuntimeError(f"No se pudo iniciar mitmproxy: {exc}") from exc

            self._current_session = CaptureSession(
                session_id=session_id,
                started_at=datetime.now(timezone.utc),
                listen_host=settings.MITMPROXY_LISTEN_HOST,
                listen_port=int(settings.MITMPROXY_LISTEN_PORT),
                pid=self._process.pid,
            )
            self._reader_thread = threading.Thread(target=self._read_stdout, daemon=True)
            self._reader_thread.start()
            self._emit_status(
                f"Captura activa en {settings.MITMPROXY_LISTEN_HOST}:{settings.MITMPROXY_LISTEN_PORT}"
            )
            self._emit_status(
                "Capture policy: hosts="
                f"{','.join(settings.API_FLOW_CAPTURE_HOST_ALLOWLIST) or '*'} "
                "paths="
                f"{','.join(settings.API_FLOW_CAPTURE_PATH_ALLOWLIST) or '*'} "
                "ignore="
                f"{','.join(settings.API_FLOW_IGNORE_HOSTS) or '-'}"
            )
            if settings.API_FLOW_IGNORE_HOSTS:
                self._emit_status(
                    "Passthrough hosts: " + ", ".join(settings.API_FLOW_IGNORE_HOSTS)
                )
            return self._current_session

    def stop_capture(self) -> None:
        with self._lock:
            process = self._process
            self._stop_event.set()
            if process is None:
                self._current_session = None
                return

            try:
                process.terminate()
                process.wait(timeout=3)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass
            finally:
                self._process = None
                self._current_session = None
                self._emit_status("Captura detenida")

    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def current_session(self) -> CaptureSession | None:
        return self._current_session

    def _read_stdout(self) -> None:
        process = self._process
        if process is None or process.stdout is None:
            return

        try:
            for line in process.stdout:
                if self._stop_event.is_set():
                    break
                clean_line = line.strip()
                if not clean_line:
                    continue
                if clean_line.startswith(_EVENT_PREFIX):
                    self._handle_event_line(clean_line[len(_EVENT_PREFIX) :])
                    continue
                self._log_console_line(clean_line)
                if "Traceback" in clean_line or "Error" in clean_line:
                    self._emit_status(f"mitmproxy: {clean_line[:200]}")
        except Exception:
            logger.exception("event=api_flow_reader_error")
            self._emit_status("Error al leer eventos de mitmproxy")
        finally:
            if not self._stop_event.is_set():
                self._emit_status("mitmproxy finalizó")
            with self._lock:
                self._process = None
                self._current_session = None

    def _handle_event_line(self, raw_payload: str) -> None:
        try:
            payload = json.loads(raw_payload)
        except Exception:
            logger.warning("event=api_flow_parse_error line=%s", raw_payload[:240])
            return

        for callback in self._event_callbacks:
            try:
                callback(payload)
            except Exception:
                logger.exception("event=api_flow_callback_error")

    def _emit_status(self, message: str) -> None:
        print(f"[api-flow] {message}", flush=True)
        logger.info("event=api_flow_status message=%s", message)
        for callback in self._status_callbacks:
            try:
                callback(message)
            except Exception:
                logger.exception("event=api_flow_status_callback_error")

    def _log_console_line(self, message: str) -> None:
        print(f"[mitmproxy] {message}", flush=True)
        logger.info("event=mitmproxy_line message=%s", message[:400])

    def _build_ignore_hosts_regex(self, hosts: list[str]) -> str | None:
        cleaned = [host.strip().lower() for host in hosts if host and host.strip()]
        if not cleaned:
            return None

        patterns = []
        for host in cleaned:
            escaped = re.escape(host.lstrip("."))
            patterns.append(rf"(^|\\.){escaped}:\\d+$")
        return "|".join(patterns)
