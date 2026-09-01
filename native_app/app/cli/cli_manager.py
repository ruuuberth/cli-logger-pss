"""Main CLI Manager - Orchestrates the interactive console interface"""
from __future__ import annotations

import logging
from rich.console import Console

from app.core.config import settings
from app.cli.menu import Menu
from app.cli.utils import print_info, print_success, print_error, _safe_print
from app.cli.concrete_commands import (
    QueryEventsCommand,
    GenerateBattleReportCommand,
    GenerateH2HReportCommand,
    InspectCharacterCommand,
    InspectRoomCommand,
    InspectBattleCommand,
    CaptureTrafficCommand,
    SystemMonitorCommand,
    SettingsCommand,
)


def _create_console(force_ascii: bool = False) -> Console:
    """Create a Console adapted to the terminal's encoding capabilities."""
    # force_ascii=True -> legacy_windows=True (ASCII-safe legacy renderer)
    # force_ascii=False -> legacy_windows=False (UTF-8 via stream)
    return Console(force_terminal=True, legacy_windows=force_ascii)


class CliManager:
    """Main CLI manager for Logger-PSS console interface"""

    def __init__(self, capture_runtime=None):
        self.console = _create_console(force_ascii=settings.CLI_FORCE_ASCII)
        self.logger = logging.getLogger(__name__)
        self.capture_runtime = capture_runtime
        
        # Initialize commands
        self.query_cmd = QueryEventsCommand(runtime=capture_runtime)
        self.report_cmd = GenerateBattleReportCommand(runtime=capture_runtime)
        self.h2h_report_cmd = GenerateH2HReportCommand(runtime=capture_runtime)
        self.char_cmd = InspectCharacterCommand()
        self.room_cmd = InspectRoomCommand()
        self.battle_cmd = InspectBattleCommand(runtime=capture_runtime)
        self.capture_cmd = CaptureTrafficCommand(runtime=capture_runtime)
        self.monitor_cmd = SystemMonitorCommand()
        self.settings_cmd = SettingsCommand()
        
        self._setup_menus()

    def _setup_menus(self) -> None:
        """Setup the menu structure"""
        self.main_menu = Menu("📊 Logger-PSS - Consola", console=self.console)
        
        # Main menu items
        self.main_menu.add_item("1", "🔍 Consultar Eventos", self.cmd_query_events)
        self.main_menu.add_item("2", "📋 Generar Reportes", self.cmd_reports)
        self.main_menu.add_item("3", "📊 Generar Reporte H2H", self.cmd_h2h_report)
        self.main_menu.add_item("4", "👤 Inspector de Tripulante", self.cmd_inspect_character)
        self.main_menu.add_item("5", "🏠 Inspector de Salas", self.cmd_inspect_rooms)
        self.main_menu.add_item("6", "🎖️ Inspector de Batalla", self.cmd_inspect_battle)
        self.main_menu.add_item("7", "📡 Captura de Tráfico", self.cmd_capture_traffic)
        self.main_menu.add_item("8", "📊 Monitor de Sistema", self.cmd_system_monitor)
        self.main_menu.add_item("9", "⚙️ Configuración", self.cmd_settings)

    def run(self) -> int:
        """Run the CLI manager"""
        try:
            print_info("Iniciando Logger-PSS Console...", console=self.console)
            _safe_print(self.console, "[bold cyan]✨ Bienvenido a Logger-PSS - Versión Consola[/bold cyan]\n")
            
            self.main_menu.run()
            print_success("¡Hasta luego!", console=self.console)
            return 0
        except Exception as e:
            print_error(f"Error fatal: {e}", console=self.console)
            self.logger.exception("Error en CLI")
            return 1

    # Command handlers
    def cmd_query_events(self) -> None:
        """Query API events"""
        self.query_cmd.execute()

    def cmd_reports(self) -> None:
        """Generate reports"""
        self.report_cmd.execute()

    def cmd_inspect_character(self) -> None:
        """Inspect character details"""
        self.char_cmd.execute()

    def cmd_inspect_rooms(self) -> None:
        """Inspect room details"""
        self.room_cmd.execute()

    def cmd_inspect_battle(self) -> None:
        """Inspect battle details"""
        self.battle_cmd.execute()

    def cmd_capture_traffic(self) -> None:
        """Start/stop traffic capture"""
        self.capture_cmd.execute()

    def cmd_system_monitor(self) -> None:
        """Monitor system resources"""
        self.monitor_cmd.execute()

    def cmd_settings(self) -> None:
        """Application settings"""
        self.settings_cmd.execute()

    def cmd_h2h_report(self) -> None:
        """Generate H2H comparative report"""
        self.h2h_report_cmd.execute()
