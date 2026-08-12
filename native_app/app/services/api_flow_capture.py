from __future__ import annotations

import hashlib
import json
import pkgutil
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from app.core.config import settings

logger = logging.getLogger(__name__)

_EVENT_PREFIX = "API_FLOW_EVENT "
EXPECTED_MITM_ADDON_SHA256 = "5b91509219cd4cfde2170a4c34c9c1d4756157fb92401407980d4378e04359f9"


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
        self._temp_addon_path: Path | None = None

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

            addon_path = self._resolve_addon_path()
            mitmproxy_binary = self._resolve_mitmproxy_binary_path()
            frozen = bool(getattr(sys, "frozen", False))

            if frozen and "_MEI" in str(addon_path):
                logger.error("event=addon_invalid_runtime_path frozen=%s addon_path=%s", frozen, addon_path)
                self._cleanup_temp_addon_path()
                raise RuntimeError(
                    "[capture_addon_unresolvable] resolved addon path points to _MEI internal bundle."
                )

            logger.info(
                "event=capture_addon_resolved frozen=%s addon_path=%s mitmproxy_binary=%s",
                frozen,
                addon_path,
                mitmproxy_binary,
            )

            session_id = uuid4().hex
            cmd = [
                str(mitmproxy_binary),
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
                self._cleanup_temp_addon_path()
                logger.exception(
                    "event=capture_proxy_missing mitm_binary=%s addon_path=%s",
                    mitmproxy_binary,
                    addon_path,
                )
                raise RuntimeError(
                    "[capture_proxy_missing] No se encontró mitmproxy. "
                    "Instala mitmproxy o usa el paquete portable que lo incluye."
                ) from exc
            except Exception as exc:
                self._cleanup_temp_addon_path()
                logger.exception(
                    "event=capture_proxy_start_failed mitm_binary=%s addon_path=%s",
                    mitmproxy_binary,
                    addon_path,
                )
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
                if os.name == "nt" and process.pid:
                    # Use taskkill to ensure the process tree is terminated on Windows
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                else:
                    process.terminate()
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill()
            except Exception:
                pass
            finally:
                self._process = None
                self._current_session = None
                self._cleanup_temp_addon_path()
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
                self._cleanup_temp_addon_path()

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
        logger.info("event=api_flow_status message=%s", message)
        for callback in self._status_callbacks:
            try:
                callback(message)
            except Exception:
                logger.exception("event=api_flow_status_callback_error")

    def _log_console_line(self, message: str) -> None:
        logger.debug("event=mitmproxy_line message=%s", message[:400])

    def _build_ignore_hosts_regex(self, hosts: list[str]) -> str | None:
        cleaned = [host.strip().lower() for host in hosts if host and host.strip()]
        if not cleaned:
            return None

        patterns = []
        for host in cleaned:
            escaped = re.escape(host.lstrip("."))
            patterns.append(rf"(^|\\.){escaped}:\\d+$")
        return "|".join(patterns)

    def _resolve_addon_path(self) -> Path:
        frozen = bool(getattr(sys, "frozen", False))
        source_path = Path(__file__).resolve().parent / "mitm_api_flow_addon.py"
        if source_path.exists() and not frozen:
            logger.info("event=addon_source_resolved path=%s frozen=%s", source_path, frozen)
            return source_path

        addon_bytes = self._load_addon_bytes(source_path, frozen)
        if not addon_bytes:
            logger.error(
                "event=addon_unresolvable frozen=%s source_exists=%s",
                frozen,
                source_path.exists(),
            )
            raise RuntimeError(
                "[capture_addon_unresolvable] addon no embebido en build (source/frozen)."
            )

        self._validate_addon_integrity(addon_bytes)
        try:
            return self._write_temp_addon(addon_bytes)
        except Exception as exc:
            raise RuntimeError(f"Fallo al extraer addon mitmproxy a temporal: {exc}") from exc

    def _load_addon_bytes(self, source_path: Path, frozen: bool) -> bytes | None:
        if source_path.exists() and not frozen:
            try:
                return source_path.read_bytes()
            except Exception as exc:
                raise RuntimeError(f"No se pudo leer el addon mitmproxy desde source: {exc}") from exc
        addon_bytes = pkgutil.get_data("app.services", "mitm_api_flow_addon.py")
        if addon_bytes:
            logger.info("event=addon_embedded_loaded frozen=%s bytes=%s", frozen, len(addon_bytes))
        return addon_bytes

    def _validate_addon_integrity(self, addon_bytes: bytes) -> None:
        normalized_bytes = self._normalize_addon_bytes(addon_bytes)
        digest = hashlib.sha256(normalized_bytes).hexdigest()
        if digest != EXPECTED_MITM_ADDON_SHA256:
            logger.error(
                "event=addon_integrity_mismatch expected=%s got=%s",
                EXPECTED_MITM_ADDON_SHA256,
                digest,
            )
            raise RuntimeError("[capture_addon_integrity_mismatch] Integridad de addon inválida (SHA256 mismatch)")
        logger.info("event=addon_integrity_ok sha256=%s", digest)

    def _normalize_addon_bytes(self, addon_bytes: bytes) -> bytes:
        # Normalize line endings to avoid false mismatches across LF/CRLF checkouts.
        return addon_bytes.replace(b"\r\n", b"\n").replace(b"\r", b"\n")

    def _resolve_mitmproxy_binary_path(self) -> Path | str:
        configured = str(settings.MITMPROXY_BINARY or "").strip()
        env_has_override = "MITMPROXY_BINARY" in os.environ

        if env_has_override:
            if self._is_executable_available(configured):
                return configured
            raise RuntimeError(
                f"[capture_proxy_missing] MITMPROXY_BINARY configurado no es ejecutable: {configured}"
            )

        packaged = self._resolve_packaged_mitmproxy_path()
        if packaged is not None:
            logger.info("event=packaged_mitmproxy_resolved path=%s", packaged)
            return packaged

        if self._is_executable_available(configured):
            return configured

        raise RuntimeError(
            "[capture_proxy_missing] No se encontró mitmproxy empaquetado ni en PATH."
        )

    def _resolve_packaged_mitmproxy_path(self) -> Path | None:
        binary_name = "mitmdump.exe" if os.name == "nt" else "mitmdump"
        candidate_roots: list[Path] = []

        if getattr(sys, "frozen", False):
            candidate_roots.append(Path(sys.executable).resolve().parent)
            meipass = getattr(sys, "_MEIPASS", None)
            if meipass:
                candidate_roots.append(Path(meipass))

        candidate_roots.append(Path(__file__).resolve().parents[2])
        candidate_roots.append(Path.cwd())

        for root in candidate_roots:
            candidate = root / "third_party" / "mitmproxy" / binary_name
            if self._is_executable_available(candidate):
                return candidate
        return None

    def _is_executable_available(self, path_or_cmd: Path | str) -> bool:
        if isinstance(path_or_cmd, Path):
            return path_or_cmd.exists() and os.access(path_or_cmd, os.X_OK)
        raw = str(path_or_cmd or "").strip()
        if not raw:
            return False
        possible_path = Path(raw)
        if possible_path.is_absolute() or any(sep in raw for sep in ("/", "\\")):
            return possible_path.exists() and os.access(possible_path, os.X_OK)
        return shutil.which(raw) is not None

    def _write_temp_addon(self, addon_bytes: bytes) -> Path:
        tmp_dir = Path(tempfile.gettempdir()) / "pss_logger_addons"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        temp_path = tmp_dir / f"mitm_api_flow_addon_{uuid4().hex}.py"
        temp_path.write_bytes(addon_bytes)
        self._temp_addon_path = temp_path
        logger.info("event=addon_frozen_extracted path=%s", temp_path)
        return temp_path

    def _cleanup_temp_addon_path(self) -> None:
        path = self._temp_addon_path
        self._temp_addon_path = None
        if path is None:
            return
        try:
            if path.exists():
                path.unlink()
        except Exception:
            logger.warning("event=addon_temp_cleanup_failed path=%s", path)
