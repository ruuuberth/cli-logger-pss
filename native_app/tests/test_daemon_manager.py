"""Tests for DaemonManager (issue #31: zero test coverage)."""
from __future__ import annotations

import os
import signal
import sys
from unittest.mock import MagicMock

import pytest

from app.daemon_manager import DaemonManager


def _make_manager(tmp_path) -> DaemonManager:
    """Build a DaemonManager without running __init__ (avoids Console + home dir)."""
    dm = DaemonManager.__new__(DaemonManager)
    dm.console = MagicMock()
    dm.logger = MagicMock()
    dm.daemon_dir = tmp_path / ".logger-pss"
    dm.pid_file = dm.daemon_dir / "daemon.pid"
    dm.runtime = None
    dm._shutdown_requested = False
    return dm


# ---------------------------------------------------------------------------
# _write_pid / _read_pid / _cleanup_pid
# ---------------------------------------------------------------------------


def test_write_pid_creates_dir_and_file(tmp_path, monkeypatch) -> None:
    dm = _make_manager(tmp_path)
    written = []

    def _fake_chmod(path, mode):
        written.append((str(path), mode))

    monkeypatch.setattr(os, "chmod", _fake_chmod)
    monkeypatch.setattr(sys, "platform", "linux")

    dm._write_pid()

    assert dm.pid_file.exists()
    assert dm.pid_file.read_text().strip() == str(os.getpid())
    assert written == [(str(dm.pid_file), 0o600)]


def test_write_pid_skips_chmod_on_win32(tmp_path, monkeypatch) -> None:
    dm = _make_manager(tmp_path)
    called = []

    def _fake_chmod(path, mode):
        called.append((str(path), mode))

    monkeypatch.setattr(os, "chmod", _fake_chmod)
    monkeypatch.setattr(sys, "platform", "win32")

    dm._write_pid()

    assert dm.pid_file.exists()
    assert called == []


def test_read_pid_returns_int(tmp_path) -> None:
    dm = _make_manager(tmp_path)
    dm.daemon_dir.mkdir(parents=True, exist_ok=True)
    dm.pid_file.write_text("  4242  \n")

    assert dm._read_pid() == 4242


def test_read_pid_corrupt_raises_valueerror(tmp_path) -> None:
    dm = _make_manager(tmp_path)
    dm.daemon_dir.mkdir(parents=True, exist_ok=True)
    dm.pid_file.write_text("not-a-pid\n")

    with pytest.raises(ValueError):
        dm._read_pid()


def test_cleanup_pid_removes_file(tmp_path) -> None:
    dm = _make_manager(tmp_path)
    dm.daemon_dir.mkdir(parents=True, exist_ok=True)
    dm.pid_file.write_text("1\n")

    dm._cleanup_pid()

    assert not dm.pid_file.exists()


def test_cleanup_pid_no_file_no_error(tmp_path) -> None:
    dm = _make_manager(tmp_path)
    dm._cleanup_pid()  # must not raise


# ---------------------------------------------------------------------------
# _is_running
# ---------------------------------------------------------------------------


def test_is_running_false_when_no_pid_file(tmp_path) -> None:
    dm = _make_manager(tmp_path)
    assert dm._is_running() is False


def test_is_running_true_on_unix_when_process_exists(tmp_path, monkeypatch) -> None:
    dm = _make_manager(tmp_path)
    dm.daemon_dir.mkdir(parents=True, exist_ok=True)
    dm.pid_file.write_text("777\n")
    monkeypatch.setattr(sys, "platform", "linux")
    killed = []

    def _fake_kill(pid, sig):
        killed.append((pid, sig))

    monkeypatch.setattr(os, "kill", _fake_kill)

    assert dm._is_running() is True
    assert killed == [(777, 0)]


def test_is_running_false_on_unix_when_process_dead(tmp_path, monkeypatch) -> None:
    dm = _make_manager(tmp_path)
    dm.daemon_dir.mkdir(parents=True, exist_ok=True)
    dm.pid_file.write_text("999\n")
    monkeypatch.setattr(sys, "platform", "linux")

    def _fake_kill(pid, sig):
        raise ProcessLookupError(pid)

    monkeypatch.setattr(os, "kill", _fake_kill)

    assert dm._is_running() is False


def test_is_running_false_on_unix_when_pid_corrupt(tmp_path, monkeypatch) -> None:
    dm = _make_manager(tmp_path)
    dm.daemon_dir.mkdir(parents=True, exist_ok=True)
    dm.pid_file.write_text("garbage\n")
    monkeypatch.setattr(sys, "platform", "linux")

    assert dm._is_running() is False


def test_is_running_win32_tasklist_exact_pid(tmp_path, monkeypatch) -> None:
    """tasklist output with the exact PID -> running."""
    dm = _make_manager(tmp_path)
    dm.daemon_dir.mkdir(parents=True, exist_ok=True)
    dm.pid_file.write_text("12\n")
    monkeypatch.setattr(sys, "platform", "win32")

    def _fake_run(cmd, capture_output, text):
        class _Result:
            stdout = (
                "Nombre de la imagen                     PID Sesión        Uso de memoria\n"
                "========================= ======== ================ ============\n"
                "cmd.exe                                 12 Consola                    1     5,678 K\n"
            )

        return _Result()

    monkeypatch.setattr("subprocess.run", _fake_run)

    assert dm._is_running() is True


def test_is_running_win32_tasklist_pid_prefix_does_not_match(tmp_path, monkeypatch) -> None:
    """Regression: PID 12 must NOT match tasklist lines containing 123 or 1200."""
    dm = _make_manager(tmp_path)
    dm.daemon_dir.mkdir(parents=True, exist_ok=True)
    dm.pid_file.write_text("12\n")
    monkeypatch.setattr(sys, "platform", "win32")

    def _fake_run(cmd, capture_output, text):
        class _Result:
            stdout = (
                "Nombre de la imagen                     PID Sesión        Uso de memoria\n"
                "========================= ======== ================ ============\n"
                "cmd.exe                                 123 Consola                   1     5,678 K\n"
                "svchost.exe                            1200 Consola                   1    12,345 K\n"
            )

        return _Result()

    monkeypatch.setattr("subprocess.run", _fake_run)

    # Old code: str(12) in stdout -> True (bug). Fixed: exact PID column match -> False.
    assert dm._is_running() is False


# ---------------------------------------------------------------------------
# stop
# ---------------------------------------------------------------------------


def test_stop_when_not_running_returns_1(tmp_path, monkeypatch) -> None:
    dm = _make_manager(tmp_path)
    monkeypatch.setattr(dm, "_is_running", lambda: False)

    assert dm.stop() == 1


def test_stop_unix_sends_sigterm(tmp_path, monkeypatch) -> None:
    dm = _make_manager(tmp_path)
    monkeypatch.setattr(dm, "_is_running", lambda: True)
    monkeypatch.setattr(dm, "_read_pid", lambda: 555)
    monkeypatch.setattr(sys, "platform", "linux")

    killed = []
    monkeypatch.setattr(os, "kill", lambda pid, sig: killed.append((pid, sig)))

    assert dm.stop() == 0
    assert killed == [(555, signal.SIGTERM)]


def test_stop_win32_uses_taskkill(tmp_path, monkeypatch) -> None:
    dm = _make_manager(tmp_path)
    monkeypatch.setattr(dm, "_is_running", lambda: True)
    monkeypatch.setattr(dm, "_read_pid", lambda: 777)
    monkeypatch.setattr(sys, "platform", "win32")

    calls = []
    monkeypatch.setattr(os, "system", lambda cmd: calls.append(cmd))

    assert dm.stop() == 0
    assert calls == ["taskkill /F /PID 777 /T >nul 2>&1"]


def test_stop_process_not_found_cleans_pid(tmp_path, monkeypatch) -> None:
    dm = _make_manager(tmp_path)
    monkeypatch.setattr(dm, "_is_running", lambda: True)
    monkeypatch.setattr(dm, "_read_pid", lambda: 333)
    monkeypatch.setattr(sys, "platform", "linux")

    def _fake_kill(pid, sig):
        raise ProcessLookupError(pid)

    monkeypatch.setattr(os, "kill", _fake_kill)

    cleaned = []
    monkeypatch.setattr(dm, "_cleanup_pid", lambda: cleaned.append(True))

    assert dm.stop() == 0
    assert cleaned == [True]


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


def test_status_running(tmp_path, monkeypatch) -> None:
    dm = _make_manager(tmp_path)
    monkeypatch.setattr(dm, "_is_running", lambda: True)
    monkeypatch.setattr(dm, "_read_pid", lambda: 42)

    assert dm.status() == 0
    dm.console.print.assert_any_call("[green]✅ Daemon corriendo[/green]")
    dm.console.print.assert_any_call("  PID: 42")


def test_status_not_running_with_stale_pid(tmp_path, monkeypatch) -> None:
    dm = _make_manager(tmp_path)
    dm.daemon_dir.mkdir(parents=True, exist_ok=True)
    dm.pid_file.write_text("9\n")
    monkeypatch.setattr(dm, "_is_running", lambda: False)

    assert dm.status() == 1
    dm.console.print.assert_any_call("[red]❌ Daemon no está corriendo[/red]")
    dm.console.print.assert_any_call(
        "[yellow]⚠️ Archivo PID existe pero proceso no encontrado[/yellow]"
    )
