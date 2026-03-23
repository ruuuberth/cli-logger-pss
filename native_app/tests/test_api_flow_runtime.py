from __future__ import annotations

from types import SimpleNamespace

from app.services.api_flow_runtime import ApiFlowRuntime


class _Repo:
    def __init__(self, save_return: int = 0) -> None:
        self.save_return = save_return
        self.saved_batches: list[list[dict]] = []
        self.purge_calls = 0
        self.snapshot = {"max_event_id": 3, "max_replay_id": 4}
        self.sync_calls: list[tuple[str, int | None]] = []

    def save_events(self, events: list[dict]) -> int:
        self.saved_batches.append(list(events))
        return self.save_return

    def purge(self, retention_days: int, max_db_mb: int) -> None:
        self.purge_calls += 1

    def get_startup_sync_snapshot(self) -> dict[str, int]:
        return dict(self.snapshot)

    def backfill_response_body_cleaned(self, batch_size: int = 100, max_event_id: int | None = None) -> int:
        self.sync_calls.append(("cleaned", max_event_id))
        return 0

    def sync_battle_replays_from_api_flow(self, batch_size: int = 500, max_event_id: int | None = None) -> int:
        self.sync_calls.append(("replays", max_event_id))
        return 0

    def sync_battle_replay_children(self, batch_size: int = 200, max_replay_id: int | None = None) -> int:
        self.sync_calls.append(("children", max_replay_id))
        return 0

    def backfill_room_attributes(self, batch_size: int = 200, max_replay_id: int | None = None) -> int:
        self.sync_calls.append(("rooms", max_replay_id))
        return 0


class _CaptureManager:
    def __init__(self) -> None:
        self.event_callbacks = []
        self.status_callbacks = []
        self.running = False
        self.session = None

    def subscribe(self, callback) -> None:
        self.event_callbacks.append(callback)

    def subscribe_status(self, callback) -> None:
        self.status_callbacks.append(callback)

    def start_capture(self):
        self.running = True
        self.session = SimpleNamespace(
            session_id="session-1",
            listen_host="127.0.0.1",
            listen_port=8080,
            pid=555,
        )
        for callback in self.status_callbacks:
            callback("Captura activa en 127.0.0.1:8080")
        return self.session

    def stop_capture(self) -> None:
        self.running = False
        self.session = None
        for callback in self.status_callbacks:
            callback("Captura detenida")

    def is_running(self) -> bool:
        return self.running

    def current_session(self):
        return self.session


class _ImmediateThread:
    def __init__(self, target, daemon: bool = False, name: str | None = None) -> None:
        self.target = target

    def start(self) -> None:
        self.target()


def test_start_capture_updates_runtime_state() -> None:
    runtime = ApiFlowRuntime(repository=_Repo(), capture_manager=_CaptureManager())

    runtime.start_capture()

    state = runtime.snapshot_state()
    assert state.capture_running is True
    assert state.session_id == "session-1"
    assert state.session_host == "127.0.0.1"
    assert state.session_port == 8080


def test_enqueue_event_increments_live_count_and_pending() -> None:
    runtime = ApiFlowRuntime(repository=_Repo(), capture_manager=_CaptureManager())

    runtime.enqueue_event({"id": 1})

    state = runtime.snapshot_state()
    assert state.live_event_count == 1
    assert state.pending_count == 1


def test_flush_pending_requeues_unsaved_events() -> None:
    repo = _Repo(save_return=1)
    runtime = ApiFlowRuntime(repository=repo, capture_manager=_CaptureManager())
    runtime.enqueue_event({"id": 1})
    runtime.enqueue_event({"id": 2})
    runtime.enqueue_event({"id": 3})

    runtime.flush_pending()

    assert [event["id"] for event in runtime._pending_events] == [2, 3]
    assert runtime.snapshot_state().flush_failures == 1
    assert repo.purge_calls == 0


def test_flush_pending_purges_and_resets_failures() -> None:
    repo = _Repo(save_return=2)
    runtime = ApiFlowRuntime(repository=repo, capture_manager=_CaptureManager())
    runtime._flush_failures = 1
    runtime.enqueue_event({"id": 1})
    runtime.enqueue_event({"id": 2})

    runtime.flush_pending()

    assert runtime.snapshot_state().pending_count == 0
    assert runtime.snapshot_state().flush_failures == 0
    assert repo.purge_calls == 1


def test_pending_limit_discards_oldest_events() -> None:
    runtime = ApiFlowRuntime(repository=_Repo(save_return=0), capture_manager=_CaptureManager())
    runtime.pending_max_events = 3

    for item_id in [1, 2, 3, 4, 5]:
        runtime.enqueue_event({"id": item_id})

    assert [event["id"] for event in runtime._pending_events] == [3, 4, 5]
    assert runtime.snapshot_state().dropped_pending_events == 2


def test_startup_sync_runs_until_snapshot_limit(monkeypatch) -> None:
    repo = _Repo()
    capture = _CaptureManager()
    runtime = ApiFlowRuntime(repository=repo, capture_manager=capture)
    monkeypatch.setattr("app.services.api_flow_runtime.Thread", _ImmediateThread)
    monkeypatch.setattr("app.services.api_flow_runtime.ApiFlowRepository", lambda: repo)

    payloads: list[dict] = []
    runtime.subscribe_startup_sync_finished(payloads.append)

    runtime.start_startup_sync()

    assert payloads == [{"ok": True}]
    assert ("cleaned", 3) in repo.sync_calls
    assert ("replays", 3) in repo.sync_calls
    assert ("children", 4) in repo.sync_calls
    assert ("rooms", 4) in repo.sync_calls
    assert runtime.snapshot_state().startup_sync_running is False


def test_stop_capture_triggers_background_flush(monkeypatch) -> None:
    repo = _Repo(save_return=1)
    capture = _CaptureManager()
    runtime = ApiFlowRuntime(repository=repo, capture_manager=capture)
    monkeypatch.setattr("app.services.api_flow_runtime.Thread", _ImmediateThread)
    runtime.enqueue_event({"id": 1})

    payloads: list[dict] = []
    runtime.subscribe_stop_flush_finished(payloads.append)
    runtime.start_capture()
    runtime.stop_capture()

    assert payloads
    assert payloads[0]["ok"] is True
    assert runtime.snapshot_state().pending_count == 0
