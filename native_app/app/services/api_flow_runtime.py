from __future__ import annotations

from dataclasses import asdict, dataclass
from threading import Lock, Thread
from typing import Any, Callable

from app.core.config import settings
from app.services.api_flow_capture import ApiFlowCaptureManager
from app.services.api_flow_storage import ApiFlowRepository


@dataclass(frozen=True)
class ApiFlowRuntimeState:
    capture_running: bool
    capture_status: str
    session_id: str
    session_host: str
    session_port: int | None
    live_event_count: int
    dropped_pending_events: int
    pending_count: int
    flush_failures: int
    startup_sync_running: bool
    startup_sync_status: str
    stop_flush_running: bool


class ApiFlowRuntime:
    pending_max_events = 10_000

    def __init__(
        self,
        repository: ApiFlowRepository | None = None,
        capture_manager: ApiFlowCaptureManager | None = None,
        settings_obj: Any | None = None,
    ) -> None:
        self.repository = repository or ApiFlowRepository()
        self.capture_manager = capture_manager or ApiFlowCaptureManager()
        self.settings = settings_obj or settings
        self._pending_events: list[dict[str, Any]] = []
        self._lock = Lock()
        self._live_event_count = 0
        self._dropped_pending_events = 0
        self._flush_failures = 0
        self._last_capture_status = "detenido"
        self._startup_sync_running = False
        self._startup_sync_status = "listo"
        self._stop_flush_running = False
        self._state_callbacks: list[Callable[[ApiFlowRuntimeState], None]] = []
        self._startup_callbacks: list[Callable[[dict[str, Any]], None]] = []
        self._stop_flush_callbacks: list[Callable[[dict[str, Any]], None]] = []
        self._flush_callbacks: list[Callable[[dict[str, Any]], None]] = []
        self.capture_manager.subscribe(self.enqueue_event)
        self.capture_manager.subscribe_status(self._handle_capture_status)

    def subscribe_state(self, callback: Callable[[ApiFlowRuntimeState], None]) -> None:
        self._state_callbacks.append(callback)

    def subscribe_startup_sync_finished(self, callback: Callable[[dict[str, Any]], None]) -> None:
        self._startup_callbacks.append(callback)

    def subscribe_stop_flush_finished(self, callback: Callable[[dict[str, Any]], None]) -> None:
        self._stop_flush_callbacks.append(callback)

    def subscribe_events_flushed(self, callback: Callable[[dict[str, Any]], None]) -> None:
        self._flush_callbacks.append(callback)

    def start_capture(self) -> None:
        self.capture_manager.start_capture()
        self._emit_state()

    def stop_capture(self) -> None:
        self.capture_manager.stop_capture()
        self._emit_state()
        self.start_stop_flush()

    def toggle_capture(self) -> None:
        if self.capture_manager.is_running():
            self.stop_capture()
            return
        self.start_capture()

    def is_capture_running(self) -> bool:
        return self.capture_manager.is_running()

    def enqueue_event(self, payload: dict[str, Any]) -> None:
        with self._lock:
            self._pending_events.append(payload)
            dropped = self._enforce_pending_limit_locked()
            if dropped:
                self._dropped_pending_events += dropped
                self._last_capture_status = (
                    f"backlog limitado, descartados {self._dropped_pending_events} eventos"
                )
            self._live_event_count += 1
        self._emit_state()

    def flush_pending(self) -> None:
        payload = self._flush_pending_impl()
        if payload is not None:
            self._emit_flush(payload)
        self._emit_state()

    def start_startup_sync(self) -> None:
        with self._lock:
            if self._startup_sync_running:
                return
            self._startup_sync_running = True
            self._startup_sync_status = "inicializando..."
        self._emit_state()
        Thread(target=self._run_startup_sync_worker, daemon=True, name="startup-sync").start()

    def start_stop_flush(self) -> None:
        with self._lock:
            if self._stop_flush_running:
                return
            self._stop_flush_running = True
            self._last_capture_status = "guardando eventos pendientes..."
        self._emit_state()
        Thread(target=self._run_stop_flush_worker, daemon=True, name="stop-flush").start()

    def close(self) -> None:
        self.flush_pending()
        self.capture_manager.stop_capture()
        self._emit_state()

    def snapshot_state(self) -> ApiFlowRuntimeState:
        session = self.capture_manager.current_session()
        with self._lock:
            return ApiFlowRuntimeState(
                capture_running=self.capture_manager.is_running(),
                capture_status=self._last_capture_status,
                session_id=session.session_id if session else "-",
                session_host=session.listen_host if session else "",
                session_port=session.listen_port if session else None,
                live_event_count=self._live_event_count,
                dropped_pending_events=self._dropped_pending_events,
                pending_count=len(self._pending_events),
                flush_failures=self._flush_failures,
                startup_sync_running=self._startup_sync_running,
                startup_sync_status=self._startup_sync_status,
                stop_flush_running=self._stop_flush_running,
            )

    def _handle_capture_status(self, message: str) -> None:
        with self._lock:
            self._last_capture_status = message
        self._emit_state()

    def _run_startup_sync_worker(self) -> None:
        repo = ApiFlowRepository()
        result: dict[str, Any] = {"ok": True}
        try:
            snapshot = repo.get_startup_sync_snapshot()
            max_event_id = int(snapshot.get("max_event_id") or 0)
            while repo.backfill_response_body_cleaned(batch_size=100, max_event_id=max_event_id) > 0:
                pass
            while repo.sync_battle_replays_from_api_flow(batch_size=500, max_event_id=max_event_id) > 0:
                pass
            post_sync_snapshot = repo.get_startup_sync_snapshot()
            max_replay_id = int(post_sync_snapshot.get("max_replay_id") or 0)
            while repo.sync_battle_replay_children(batch_size=200, max_replay_id=max_replay_id) > 0:
                pass
            while repo.backfill_room_attributes(batch_size=200, max_replay_id=max_replay_id) > 0:
                pass
            result["matchup_backfill"] = repo.backfill_matchup_history_and_prune(batch_size_pairs=200)
        except Exception as exc:
            result = {"ok": False, "error": str(exc)}
        with self._lock:
            self._startup_sync_running = False
            self._startup_sync_status = "listo" if result.get("ok", True) else f"error ({result.get('error', 'desconocido')})"
        self._emit_state()
        for callback in self._startup_callbacks:
            callback(result)

    def _run_stop_flush_worker(self) -> None:
        payload = self._flush_pending_impl(final_flush=True)
        with self._lock:
            self._stop_flush_running = False
        self._emit_state()
        for callback in self._stop_flush_callbacks:
            callback(payload or {"ok": True, "message": f"Estado: {self.snapshot_state().capture_status}"})

    def _flush_pending_impl(self, *, final_flush: bool = False) -> dict[str, Any] | None:
        with self._lock:
            if not self._pending_events:
                if final_flush:
                    return {"ok": True, "message": f"Estado: {self._last_capture_status}"}
                return None
            pending = list(self._pending_events)
            self._pending_events.clear()

        try:
            saved_count = self.repository.save_events(pending)
            if saved_count < len(pending):
                unsaved = pending[max(0, saved_count) :]
                with self._lock:
                    self._flush_failures += 1
                    self._pending_events = unsaved + self._pending_events
                    dropped = self._enforce_pending_limit_locked()
                    if dropped:
                        self._dropped_pending_events += dropped
                    self._last_capture_status = (
                        "error de persistencia, reintentos="
                        f"{self._flush_failures}, pendientes={len(self._pending_events)}"
                    )
                return {"ok": False, "message": f"Estado: {self.snapshot_state().capture_status}"}

            self.repository.purge(
                retention_days=self.settings.API_FLOW_RETENTION_DAYS,
                max_db_mb=self.settings.API_FLOW_MAX_DB_MB,
            )
            with self._lock:
                if self._flush_failures:
                    self._flush_failures = 0
            return {
                "ok": True,
                "saved_count": saved_count,
                "message": f"Estado: {self.snapshot_state().capture_status}",
            }
        except Exception as exc:
            with self._lock:
                self._pending_events = pending + self._pending_events
                dropped = self._enforce_pending_limit_locked()
                if dropped:
                    self._dropped_pending_events += dropped
                self._flush_failures += 1
                self._last_capture_status = f"error de persistencia ({exc})"
            return {"ok": False, "message": f"Estado: {self.snapshot_state().capture_status}"}

    def _enforce_pending_limit_locked(self) -> int:
        if len(self._pending_events) <= self.pending_max_events:
            return 0
        dropped = len(self._pending_events) - self.pending_max_events
        del self._pending_events[:dropped]
        return dropped

    def _emit_state(self) -> None:
        state = self.snapshot_state()
        for callback in self._state_callbacks:
            callback(state)

    def _emit_flush(self, payload: dict[str, Any]) -> None:
        for callback in self._flush_callbacks:
            callback(payload)

    @staticmethod
    def state_to_payload(state: ApiFlowRuntimeState) -> dict[str, Any]:
        return asdict(state)
