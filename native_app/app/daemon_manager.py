"""Daemon Manager - Handles background capture without UI"""
from __future__ import annotations

import logging
from pathlib import Path
from rich.console import Console


class DaemonManager:
    """Manages daemon mode - background capture only"""

    def __init__(self):
        self.console = Console()
        self.logger = logging.getLogger(__name__)
        self.daemon_dir = Path.home() / ".logger-pss"
        self.pid_file = self.daemon_dir / "daemon.pid"

    def run(self) -> int:
        """Run daemon mode"""
        try:
            self.console.print("[bold cyan]📡 Iniciando Logger-PSS en modo Daemon[/bold cyan]")
            self.console.print("[yellow]⚠️ Funcionalidad en desarrollo[/yellow]")
            self.console.print("[cyan]ℹ️ El daemon capturará tráfico en background sin interfaz[/cyan]")
            return 0
        except Exception as e:
            self.logger.exception(f"Error en daemon: {e}")
            return 1
