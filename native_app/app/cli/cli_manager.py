"""Main CLI Manager - Orchestrates the interactive console interface"""
from __future__ import annotations

import logging
from rich.console import Console
from app.cli.menu import Menu, print_info, print_success, print_error
from app.cli.concrete_commands import (
    QueryEventsCommand,
    GenerateBattleReportCommand,
    InspectCharacterCommand,
    InspectRoomCommand,
    InspectBattleCommand,
    CaptureTrafficCommand,
    SystemMonitorCommand,
)


class CliManager:
    """Main CLI manager for Logger-PSS console interface"""

    def __init__(self, capture_runtime=None):
        self.console = Console()
        self.logger = logging.getLogger(__name__)
        self.capture_runtime = capture_runtime
        
        # Initialize commands
        self.query_cmd = QueryEventsCommand()
        self.report_cmd = GenerateBattleReportCommand()
        self.char_cmd = InspectCharacterCommand()
        self.room_cmd = InspectRoomCommand()
        self.battle_cmd = InspectBattleCommand()
        self.capture_cmd = CaptureTrafficCommand(runtime=capture_runtime)
        self.monitor_cmd = SystemMonitorCommand()
        
        self._setup_menus()

    def _setup_menus(self) -> None:
        """Setup the menu structure"""
        self.main_menu = Menu("📊 Logger-PSS - Consola", console=self.console)
        
        # Main menu items
        self.main_menu.add_item("1", "🔍 Consultar Eventos", self.cmd_query_events)
        self.main_menu.add_item("2", "📋 Generar Reportes", self.cmd_reports)
        self.main_menu.add_item("3", "👤 Inspector de Tripulante", self.cmd_inspect_character)
        self.main_menu.add_item("4", "🏠 Inspector de Salas", self.cmd_inspect_rooms)
        self.main_menu.add_item("5", "🎖️ Inspector de Batalla", self.cmd_inspect_battle)
        self.main_menu.add_item("6", "📡 Captura de Tráfico", self.cmd_capture_traffic)
        self.main_menu.add_item("7", "📊 Monitor de Sistema", self.cmd_system_monitor)
        self.main_menu.add_item("8", "⚙️ Configuración", self.cmd_settings)

    def run(self) -> int:
        """Run the CLI manager"""
        try:
            print_info("Iniciando Logger-PSS Console...")
            self.console.print("[bold cyan]✨ Bienvenido a Logger-PSS - Versión Consola[/bold cyan]\n")
            
            self.main_menu.run()
            print_success("¡Hasta luego!")
            return 0
        except Exception as e:
            print_error(f"Error fatal: {e}")
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
        print_info("Funcionalidad: Configuración")
        print_info("Estado: En desarrollo")
