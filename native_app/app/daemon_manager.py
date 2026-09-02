"""Daemon Manager - Handles background capture without UI"""
from __future__ import annotations

import logging
import os
import signal
import sys
import time
from pathlib import Path
from typing import Optional

from rich.console import Console

from app.services.api_flow_runtime import ApiFlowRuntime
from app.core.config import settings


def _create_daemon_console() -> Console:
    """Create a Console adapted to the terminal's encoding capabilities for daemon."""
    return Console(force_terminal=True, legacy_windows=settings.CLI_FORCE_ASCII)


class DaemonManager:
    """Manages daemon mode - background capture only"""

    def __init__(self):
        self.console = _create_daemon_console()
        self.logger = logging.getLogger(__name__)
        self.daemon_dir = Path.home() / ".logger-pss"
        self.pid_file = self.daemon_dir / "daemon.pid"
        self.runtime: Optional[ApiFlowRuntime] = None
        self._shutdown_requested = False

    def run(self) -> int:
        """Run daemon mode - starts capture and blocks until shutdown"""
        try:
            self._setup_signal_handlers()
            
            # Check if already running
            if self._is_running():
                pid = self._read_pid()
                self.console.print(f"[yellow]⚠️ Daemon ya está ejecutándose (PID: {pid})[/yellow]")
                return 1

            # Create PID file
            self._write_pid()

            self.console.print("[bold cyan]📡 Iniciando Logger-PSS en modo Daemon[/bold cyan]")
            self.console.print(f"[cyan]ℹ️ PID: {os.getpid()}[/cyan]")
            self.console.print(f"[cyan]ℹ️ Directorio PID: {self.daemon_dir}[/cyan]")
            self.console.print("[cyan]ℹ️ Presione Ctrl+C para detener[/cyan]")

            # Initialize and start capture
            self.runtime = ApiFlowRuntime()
            self.runtime.start_capture()
            self.logger.info("event=daemon_started pid=%s", os.getpid())

            # Main loop - wait for shutdown signal
            while not self._shutdown_requested:
                time.sleep(1)
                # Periodic status logging (optional, could be controlled by config)
                # self._log_status()

            # Graceful shutdown
            self._shutdown()
            return 0

        except Exception as e:
            self.logger.exception("Error en daemon: %s", e)
            self.console.print(f"[red]❌ Error: {e}[/red]")
            self._cleanup_pid()
            return 1

    def stop(self) -> int:
        """Stop a running daemon"""
        if not self._is_running():
            self.console.print("[yellow]⚠️ Daemon no está en ejecución[/yellow]")
            return 1

        pid = self._read_pid()
        try:
            if sys.platform == "win32":
                # On Windows, use taskkill
                os.system(f"taskkill /F /PID {pid} /T >nul 2>&1")
            else:
                os.kill(pid, signal.SIGTERM)
            self.console.print("[green]✅ Señal de parada enviada[/green]")
            return 0
        except ProcessLookupError:
            self.console.print("[yellow]⚠️ Proceso no encontrado, limpiando PID[/yellow]")
            self._cleanup_pid()
            return 0
        except Exception as e:
            self.logger.exception("Error deteniendo daemon: %s", e)
            self.console.print(f"[red]❌ Error: {e}[/red]")
            return 1

    def status(self) -> int:
        """Show daemon status"""
        if self._is_running():
            pid = self._read_pid()
            self.console.print("[green]✅ Daemon corriendo[/green]")
            self.console.print(f"  PID: {pid}")
            # Could add more stats here if runtime is accessible
            return 0
        else:
            self.console.print("[red]❌ Daemon no está corriendo[/red]")
            if self.pid_file.exists():
                self.console.print("[yellow]⚠️ Archivo PID existe pero proceso no encontrado[/yellow]")
            return 1

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown"""
        def signal_handler(signum, frame):
            self.logger.info("Received signal %s, initiating shutdown", signum)
            self._shutdown_requested = True

        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        if hasattr(signal, 'SIGHUP'):
            signal.signal(signal.SIGHUP, signal_handler)

    def _is_running(self) -> bool:
        """Check if daemon process is running"""
        if not self.pid_file.exists():
            return False
        try:
            pid = self._read_pid()
            if sys.platform == "win32":
                # Check if process exists on Windows
                import subprocess
                result = subprocess.run(
                    ["tasklist", "/FI", f"PID eq {pid}"],
                    capture_output=True, text=True
                )
                return str(pid) in result.stdout
            else:
                # On Unix, signal 0 checks if process exists
                os.kill(pid, 0)
                return True
        except (ProcessLookupError, OSError, ValueError):
            return False

    def _read_pid(self) -> int:
        """Read PID from file"""
        with open(self.pid_file, "r") as f:
            return int(f.read().strip())

    def _write_pid(self) -> None:
        """Write current PID to file"""
        self.daemon_dir.mkdir(parents=True, exist_ok=True)
        with open(self.pid_file, "w") as f:
            f.write(str(os.getpid()))
        # Restrict permissions on Unix
        if sys.platform != "win32":
            os.chmod(self.pid_file, 0o600)

    def _cleanup_pid(self) -> None:
        """Remove PID file"""
        try:
            if self.pid_file.exists():
                self.pid_file.unlink()
        except Exception:
            pass

    def _shutdown(self) -> None:
        """Graceful shutdown"""
        self.logger.info("Shutting down daemon...")
        self.console.print("\n[cyan]🛑 Deteniendo daemon...[/cyan]")
        
        if self.runtime:
            try:
                self.runtime.stop_capture()
                self.logger.info("Capture stopped, flushing pending events...")
            except Exception as e:
                self.logger.exception("Error stopping capture: %s", e)

        self._cleanup_pid()
        self.console.print("[green]✅ Daemon detenido correctamente[/green]")