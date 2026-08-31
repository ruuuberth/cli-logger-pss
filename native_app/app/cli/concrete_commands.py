"""Concrete CLI Commands for Logger-PSS"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from rich.table import Table
from rich.console import Console
from rich.prompt import Prompt, Confirm
from typing import Any

from app.cli.commands import CliCommand
from app.cli.menu import Menu
from app.cli.utils import (
    print_info,
    print_success,
    print_error,
    print_warning,
    confirm_action,
    prompt_input,
    clear_console,
)
from app.cli.cli_services import ApiFlowCliService, CharacterCliService, RoomCliService
from app.reporting.report_generator import (
    ReportConfig,
    ExcelReportGenerator,
    CsvReportGenerator,
    JsonReportGenerator,
)
from app.reporting.report_templates import BattleReplayTemplate
from app.services.process_resource_monitor import ProcessResourceMonitor
from app.services.api_flow_runtime import ApiFlowRuntime
from app.core.config import settings


class QueryEventsCommand(CliCommand):
    """Query and filter API events"""

    def __init__(self, runtime=None):
        super().__init__("query_events", "Consultar Eventos API")
        self.runtime = runtime
        self.service = ApiFlowCliService()
        self.console = Console()

    def execute(self, args: list[str] = None) -> int:
        """Execute query command"""
        try:
            clear_console()
            
            saved_count = 0
            if self.runtime:
                print_info("💾 Sincronizando eventos pendientes...")
                result = self.runtime.flush_pending()
                if result and result.get("ok"):
                    saved_count = result.get("saved_count", 0)
                    print_success(f"✅ {saved_count} eventos sincronizados")
                elif result and not result.get("ok"):
                    print_warning(f"⚠️ Flush falló: {result.get('message', 'error desconocido')}")
                    print_info("⚠️ Continuando con datos locales - resultados pueden estar desactualizados")

            print_info("🔍 Consultar Eventos API")
            
            # Get search filter
            search = prompt_input("Filtro (atacante/defensor/battle_id) [Enter = sin filtro]", default="")
            
            # Date range filters
            print_info("Filtros opcionales (Enter para omitir):")
            date_from_str = prompt_input("Fecha desde (YYYY-MM-DD) [Enter = sin filtro]", default="")
            date_to_str = prompt_input("Fecha hasta (YYYY-MM-DD) [Enter = sin filtro]", default="")
            
            # Outcome filter
            outcome = prompt_input("Resultado (VICTORY/DEFEAT/DRAW) [Enter = todos]", default="")
            outcome = outcome.upper() if outcome else None
            if outcome and outcome not in ("VICTORY", "DEFEAT", "DRAW"):
                outcome = None
            
            # Trophy range filters
            trophy_min_str = prompt_input("Trofeos mínimos [Enter = sin filtro]", default="")
            trophy_max_str = prompt_input("Trofeos máximos [Enter = sin filtro]", default="")
            
            time_from = None
            time_to = None
            trophy_min = None
            trophy_max = None
            
            try:
                if date_from_str:
                    time_from = datetime.strptime(date_from_str, "%Y-%m-%d")
                if date_to_str:
                    time_to = datetime.strptime(date_to_str, "%Y-%m-%d")
                if trophy_min_str:
                    trophy_min = int(trophy_min_str)
                if trophy_max_str:
                    trophy_max = int(trophy_max_str)
            except ValueError:
                print_error("Formato de fecha o número inválido")
                return 1

            # Query first page
            page = self.service.query_events(
                search=search,
                page=0,
                page_size=20,
                time_from=time_from,
                time_to=time_to,
                outcome=outcome,
                trophy_min=trophy_min,
                trophy_max=trophy_max,
            )
            
            if not page.rows:
                print_warning("No se encontraron eventos")
                return 0
            
            # Display table
            table = Table(title=f"📋 Eventos - Total: {page.total}", show_header=True)
            table.add_column("Hora", style="cyan")
            table.add_column("Atacante", style="magenta")
            table.add_column("Defensor", style="magenta")
            table.add_column("Resultado", style="green")
            table.add_column("Botín", style="yellow")
            table.add_column("Copas", style="blue")
            table.add_column("Battle ID", style="white")
            
            for row in page.rows:
                table.add_row(
                    row.captured_at_label,
                    row.attacker_label,
                    row.defender_label,
                    row.outcome_label,
                    row.loot_label,
                    row.trophy_delta_label,
                    row.battle_id_label,
                )
            
            self.console.print(table)
            print_info(f"Mostrando página {page.page + 1} de {page.max_page + 1}")
            
            return 0
        except Exception as e:
            print_error(f"Error consultando eventos: {e}")
            return 1


class GenerateBattleReportCommand(CliCommand):
    """Generate battle report"""

    def __init__(self, runtime=None):
        super().__init__("generate_report", "Generar Reporte de Batallas")
        self.runtime = runtime
        self.service = ApiFlowCliService()
        self.console = Console()

    def execute(self, args: list[str] = None) -> int:
        """Execute report generation"""
        try:
            clear_console()
            
            saved_count = 0
            if self.runtime:
                print_info("💾 Sincronizando eventos pendientes...")
                result = self.runtime.flush_pending()
                if result and result.get("ok"):
                    saved_count = result.get("saved_count", 0)
                    print_success(f"✅ {saved_count} eventos sincronizados")
                elif result and not result.get("ok"):
                    print_warning(f"⚠️ Flush falló: {result.get('message', 'error desconocido')}")
                    print_info("⚠️ Continuando con datos locales - resultados pueden estar desactualizados")

            print_info("📋 Generando reporte de batallas...")

            # Parse args for non-interactive use
            opts: dict[str, str] = {}
            if args:
                for a in args:
                    if a.startswith("--"):
                        if "=" in a:
                            k, v = a[2:].split("=", 1)
                            opts[k] = v
                        else:
                            opts[a[2:]] = "true"

            # Parameters: allow override via args or prompt
            search = opts.get("search") or (prompt_input("Filtro (atacante/defensor/battle_id) [Enter = todos]", default="") if opts.get("non-interactive") is None else "")

            # Date range filters
            print_info("Filtros opcionales (Enter para omitir):")
            date_from_str = opts.get("date-from") or (prompt_input("Fecha desde (YYYY-MM-DD) [Enter = sin filtro]", default="") if opts.get("non-interactive") is None else "")
            date_to_str = opts.get("date-to") or (prompt_input("Fecha hasta (YYYY-MM-DD) [Enter = sin filtro]", default="") if opts.get("non-interactive") is None else "")
            
            # Outcome filter
            outcome = opts.get("outcome") or (prompt_input("Resultado (VICTORY/DEFEAT/DRAW) [Enter = todos]", default="") if opts.get("non-interactive") is None else "")
            outcome = outcome.upper() if outcome else None
            if outcome and outcome not in ("VICTORY", "DEFEAT", "DRAW"):
                outcome = None
            
            # Trophy range filters
            trophy_min_str = opts.get("trophy-min") or (prompt_input("Trofeos mínimos [Enter = sin filtro]", default="") if opts.get("non-interactive") is None else "")
            trophy_max_str = opts.get("trophy-max") or (prompt_input("Trofeos máximos [Enter = sin filtro]", default="") if opts.get("non-interactive") is None else "")
            
            time_from = None
            time_to = None
            trophy_min = None
            trophy_max = None
            
            try:
                if date_from_str:
                    time_from = datetime.strptime(date_from_str, "%Y-%m-%d")
                if date_to_str:
                    time_to = datetime.strptime(date_to_str, "%Y-%m-%d")
                if trophy_min_str:
                    trophy_min = int(trophy_min_str)
                if trophy_max_str:
                    trophy_max = int(trophy_max_str)
            except ValueError:
                print_error("Formato de fecha o número inválido")
                return 1

            # Format choice
            format_choice = opts.get("format") or prompt_input("Formato (excel/csv/json) [excel]", default="excel")
            if format_choice not in ["excel", "csv", "json"]:
                print_error("Formato no válido")
                return 1

            # Query data
            print_info("Obteniendo datos...")
            limit = int(opts.get("limit", "1000"))
            page = self.service.query_events(
                search=search,
                page=0,
                page_size=limit,
                time_from=time_from,
                time_to=time_to,
                outcome=outcome,
                trophy_min=trophy_min,
                trophy_max=trophy_max,
            )
            
            if not page.rows:
                print_warning("No hay datos para reportar")
                return 0
            
            # Convert to report format
            rows = [
                BattleReplayTemplate.row_from_battle({
                    "battle_id": row.battle_id_label,
                    "attacker_name": row.attacker_label,
                    "defender_name": row.defender_label,
                    "outcome": row.outcome_label,
                    "loot": row.loot_label,
                    "trophy_delta": row.trophy_delta_label,
                    "captured_at": row.captured_at_label,
                })
                for row in page.rows
            ]
            
            # Output options (args override prompts)
            default_output = Path(opts.get("output-dir") or Path.home() / "Desktop" / "Logger-PSS Reports")
            if opts.get("non-interactive"):
                output_path = Path(default_output).expanduser()
                filename_input = opts.get("filename") or "Reporte Batallas"
                include_ts = not (opts.get("no-timestamp") in ("true", "1", "yes"))
            else:
                out_input = prompt_input(f"Carpeta de salida [{default_output}]", default=str(default_output))
                output_path = Path(out_input).expanduser()
                filename_input = prompt_input("Nombre base del archivo [Reporte Batallas]", default="Reporte Batallas")
                include_ts_input = prompt_input("Incluir timestamp en nombre? (y/n) [y]", default="y")
                include_ts = include_ts_input.strip().lower() in ("y", "yes", "")

            config = ReportConfig(
                title=filename_input,
                output_path=output_path,
                include_timestamp=include_ts,
                format=format_choice,
            )
            
            if format_choice == "excel":
                generator = ExcelReportGenerator(config)
            elif format_choice == "csv":
                generator = CsvReportGenerator(config)
            else:
                generator = JsonReportGenerator(config)
            
            generator.add_rows(rows)
            output_file = generator.generate()
            
            print_success(f"✅ Reporte generado: {output_file}")
            return 0
        except Exception as e:
            print_error(f"Error generando reporte: {e}")
            return 1


class InspectCharacterCommand(CliCommand):
    """Inspect character details"""

    def __init__(self):
        super().__init__("inspect_char", "Inspeccionar Tripulante")
        self.service = CharacterCliService()
        self.console = Console()

    def execute(self, args: list[str] = None) -> int:
        """Execute character inspection"""
        try:
            clear_console()
            print_info("👤 Inspector de Tripulantes")

            battle_id = prompt_input("Ingrese battle_replay_id (o Enter para cancelar)", default="")
            if not battle_id:
                print_info("Cancelado")
                return 0
            try:
                rid = int(battle_id)
            except ValueError:
                print_error("ID inválido")
                return 1

            characters = self.service.list_characters(rid)
            if not characters:
                print_warning("No se encontraron tripulantes")
                return 0

            print_info("Tripulantes encontrados:")
            for i, c in enumerate(characters):
                side = c.get("side", "?")
                print(f"  [{i}] {side} — {c.get('name', '-')} (Design: {c.get('design_name', '-')}, Lv {c.get('level', '-')}, Ship: {c.get('ship_id', '-')})")

            selection = prompt_input("Seleccione índice (o Enter para cancelar)", default="")
            if not selection:
                print_info("Cancelado")
                return 0
            try:
                idx = int(selection)
                if idx < 0 or idx >= len(characters):
                    raise ValueError
            except ValueError:
                print_error("Selección inválida")
                return 1

            selected = characters[idx]
            char_id = selected.get("id")
            side = selected.get("side")
            detail = self.service.inspect_character(char_id, rid, side)
            if "error" in detail:
                print_error(detail["error"])
                return 1

            self._render_character_detail(detail)
            return 0
        except Exception as e:
            print_error(f"Error inspeccionando tripulante: {e}")
            return 1

    def _render_character_detail(self, detail: dict) -> None:
        """Render character details as Rich tables"""
        # Basic info
        info = Table(title=f"Tripulante {detail.get('name', '-')} ({detail.get('design_name', '-')})", show_header=True, header_style="bold cyan")
        info.add_column("Campo", style="bold")
        info.add_column("Valor")
        info.add_row("ID", str(detail.get("character_id", "-")))
        info.add_row("Bando", detail.get("side", "-"))
        info.add_row("Nivel", str(detail.get("level", "-")))
        info.add_row("XP", str(detail.get("xp", "-")))
        info.add_row("Ship ID", str(detail.get("ship_id", "-")))
        self.console.print(info)

        # Stats
        stats = detail.get("stats", {})
        if stats:
            stats_table = Table(title="Estadísticas", show_header=True, header_style="bold cyan")
            stats_table.add_column("Stat", style="bold")
            stats_table.add_column("Valor")
            for k, v in stats.items():
                stats_table.add_row(k, str(v))
            self.console.print(stats_table)

        # Actions
        actions = detail.get("actions", [])
        if actions:
            act_table = Table(title="Acciones", show_header=True, header_style="bold cyan")
            act_table.add_column("#", style="bold")
            act_table.add_column("Action ID")
            act_table.add_column("Acción")
            act_table.add_column("Condition ID")
            act_table.add_column("Condición")
            act_table.add_column("Character Action ID")
            for a in actions:
                act_table.add_row(
                    a.get("index", "-"),
                    a.get("action_id", "-"),
                    a.get("action_label", "-"),
                    a.get("condition_id", "-"),
                    a.get("condition_label", "-"),
                    a.get("character_action_id", "-"),
                )
            self.console.print(act_table)

        # Items
        items = detail.get("items", [])
        if items:
            item_table = Table(title="Items", show_header=True, header_style="bold cyan")
            item_table.add_column("#", style="bold")
            item_table.add_column("Item ID")
            item_table.add_column("Design ID")
            item_table.add_column("Nombre")
            item_table.add_column("Cantidad")
            item_table.add_column("Bonus Tipo")
            item_table.add_column("Bonus Valor")
            for it in items:
                item_table.add_row(
                    it.get("index", "-"),
                    it.get("item_id", "-"),
                    it.get("item_design_id", "-"),
                    it.get("item_name", "-"),
                    it.get("quantity", "-"),
                    it.get("bonus_type", "-"),
                    it.get("bonus_value", "-"),
                )
            self.console.print(item_table)


class InspectRoomCommand(CliCommand):
    """Inspect room details"""

    def __init__(self):
        super().__init__("inspect_room", "Inspeccionar Sala")
        self.service = RoomCliService()
        self.console = Console()

    def execute(self, args: list[str] = None) -> int:
        """Execute room inspection"""
        try:
            clear_console()
            print_info("🏠 Inspector de Salas")

            battle_id = prompt_input("Ingrese battle_replay_id (o Enter para cancelar)", default="")
            if not battle_id:
                print_info("Cancelado")
                return 0
            try:
                rid = int(battle_id)
            except ValueError:
                print_error("ID inválido")
                return 1

            rooms = self.service.list_rooms(rid)
            if not rooms:
                print_warning("No se encontraron salas")
                return 0

            print_info("Salas encontradas:")
            for i, r in enumerate(rooms):
                side = r.get("side", "?")
                print(f"  [{i}] {side} — {r.get('design_name', '-')} (Room ID: {r.get('room_id', '-')}, Ship: {r.get('ship_id', '-')}, Row: {r.get('row', '-')}, Col: {r.get('column', '-')})")

            selection = prompt_input("Seleccione índice (o Enter para cancelar)", default="")
            if not selection:
                print_info("Cancelado")
                return 0
            try:
                idx = int(selection)
                if idx < 0 or idx >= len(rooms):
                    raise ValueError
            except ValueError:
                print_error("Selección inválida")
                return 1

            selected = rooms[idx]
            room_id = selected.get("id")
            side = selected.get("side")
            detail = self.service.inspect_room(room_id, rid, side)
            if "error" in detail:
                print_error(detail["error"])
                return 1

            self._render_room_detail(detail)
            return 0
        except Exception as e:
            print_error(f"Error inspeccionando sala: {e}")
            return 1

    def _render_room_detail(self, detail: dict) -> None:
        """Render room details as Rich tables"""
        # Basic info
        info = Table(title=f"Sala {detail.get('design_name', '-')} (Room ID: {detail.get('room_id_num', '-')})", show_header=True, header_style="bold cyan")
        info.add_column("Campo", style="bold")
        info.add_column("Valor")
        info.add_row("ID", str(detail.get("room_id", "-")))
        info.add_row("Bando", detail.get("side", "-"))
        info.add_row("Ship ID", str(detail.get("ship_id", "-")))
        info.add_row("Fila", str(detail.get("row", "-")))
        info.add_row("Columna", str(detail.get("column", "-")))
        info.add_row("Estado", detail.get("room_status", "-"))
        self.console.print(info)

        # Actions
        actions = detail.get("actions", [])
        if actions:
            act_table = Table(title="Acciones de la Sala", show_header=True, header_style="bold cyan")
            act_table.add_column("#", style="bold")
            act_table.add_column("Action Type ID")
            act_table.add_column("Acción")
            act_table.add_column("Condition Type ID")
            act_table.add_column("Condición")
            act_table.add_column("Room Action ID")
            for a in actions:
                act_table.add_row(
                    a.get("index", "-"),
                    a.get("action_type_id", "-"),
                    a.get("action_label", "-"),
                    a.get("condition_type_id", "-"),
                    a.get("condition_label", "-"),
                    a.get("room_action_id", "-"),
                )
            self.console.print(act_table)
        else:
            print_info("Sin acciones registradas.")


class InspectBattleCommand(CliCommand):
    """Inspect battle details by replay id"""

    def __init__(self, runtime=None):
        super().__init__("inspect_battle", "Inspeccionar Batalla")
        self.runtime = runtime
        self.service = ApiFlowCliService()
        self.console = Console()

    def execute(self, args: list[str] | None = None) -> int:
        try:
            clear_console()
            
            saved_count = 0
            if self.runtime:
                print_info("💾 Sincronizando eventos pendientes...")
                result = self.runtime.flush_pending()
                if result and result.get("ok"):
                    saved_count = result.get("saved_count", 0)
                    print_success(f"✅ {saved_count} eventos sincronizados")
                elif result and not result.get("ok"):
                    print_warning(f"⚠️ Flush falló: {result.get('message', 'error desconocido')}")
                    print_info("⚠️ Continuando con datos locales - resultados pueden estar desactualizados")

            print_info("🎖️ Inspector de Batalla")
            battle_id = prompt_input("Ingrese battle_replay_id (o Enter para cancelar)", default="")
            if not battle_id:
                print_info("Cancelado")
                return 0
            try:
                rid = int(battle_id)
            except ValueError:
                print_error("ID inválido")
                return 1

            detail = self.service.get_battle_detail(rid)
            if not detail:
                print_warning("No se encontró detalle para ese ID")
                return 0

            # Pretty print keys
            for k, v in detail.items():
                self.console.print(f"[bold]{k}[/bold]: {v}")
            return 0
        except Exception as e:
            print_error(f"Error inspeccionando batalla: {e}")
            return 1


class SettingsCommand(CliCommand):
    """Manage application settings"""

    SETTINGS_CATEGORIES = {
        "Database": [
            "DATABASE_URL",
        ],
        "API PixelStarships": [
            "PSS_API_BASE_URL",
            "PSS_API_REQUEST_TIMEOUT_SECONDS",
            "PSS_CHECKSUM_KEY",
            "DESIGNS_CACHE_TTL_SECONDS",
            "ITEMS_API_CACHE_TTL_SECONDS",
            "BATTLE_REPORT_CACHE_TTL_SECONDS",
        ],
        "Captura (mitmproxy)": [
            "API_FLOW_ENABLED",
            "MITMPROXY_BINARY",
            "MITMPROXY_LISTEN_HOST",
            "MITMPROXY_LISTEN_PORT",
            "API_FLOW_BODY_MAX_CHARS",
            "API_FLOW_RETENTION_DAYS",
            "API_FLOW_MAX_DB_MB",
            "API_FLOW_CAPTURE_HTTPS",
            "API_FLOW_IGNORE_HOSTS",
            "API_FLOW_CAPTURE_HOST_ALLOWLIST",
            "API_FLOW_CAPTURE_PATH_ALLOWLIST",
        ],
        "Reportes": [
            "REPORT_ENABLE",
            "REPORT_OUTPUT_DIR",
            "REPORT_DEFAULT_FORMAT",
            "REPORT_INCLUDE_TIMESTAMP",
            "REPORT_FILENAME_BASE",
        ],
        "CLI": [
            "CLI_NONINTERACTIVE",
            "CLI_FORCE_ASCII",
        ],
        "Logging": [
            "LOG_LEVEL",
            "LOG_FILE",
        ],
    }

    def __init__(self):
        super().__init__("settings", "Configuración")
        self.console = Console()
        self.env_path = Path(__file__).resolve().parents[2] / ".env"

    def execute(self, args: list[str] = None) -> int:
        try:
            clear_console()
            print_info("⚙️ Configuración de Logger-PSS")
            print_info(f"Archivo .env: {self.env_path}")
            print_info(f"Existe: {'Sí' if self.env_path.exists() else 'No (usando defaults)'}")

            while True:
                self._show_main_menu()
                choice = prompt_input("Opción (1-5, q=salir)", default="")
                choice = choice.strip().lower()

                if choice in ("q", "quit", "exit", "5"):
                    print_info("Volviendo al menú principal...")
                    break
                elif choice == "1":
                    self._show_all_settings()
                elif choice == "2":
                    self._edit_setting()
                elif choice == "3":
                    self._show_env_file()
                elif choice == "4":
                    self._create_env_example()
                else:
                    print_warning("Opción inválida")

            return 0
        except Exception as e:
            print_error(f"Error en configuración: {e}")
            return 1

    def _show_main_menu(self) -> None:
        print("\n[bold]Menú de Configuración:[/bold]")
        print("  1. Ver todas las configuraciones")
        print("  2. Editar una configuración")
        print("  3. Ver archivo .env completo")
        print("  4. Crear .env desde ejemplo")
        print("  5. Volver (o 'q')")

    def _show_all_settings(self) -> None:
        print("\n[bold cyan]Configuración actual:[/bold cyan]")
        for category, keys in self.SETTINGS_CATEGORIES.items():
            table = Table(title=f"📂 {category}", show_header=True, header_style="bold cyan")
            table.add_column("Clave", style="bold")
            table.add_column("Valor")
            table.add_column("Tipo")
            
            for key in keys:
                value = getattr(settings, key, "N/A")
                if isinstance(value, list):
                    display_value = json.dumps(value, ensure_ascii=False)
                else:
                    display_value = str(value)
                
                # Mask sensitive values
                if "KEY" in key.upper() or "PASSWORD" in key.upper() or "SECRET" in key.upper():
                    display_value = "***MASKED***" if display_value != "" else "(vacío)"
                
                value_type = type(value).__name__
                table.add_row(key, display_value, value_type)
            
            self.console.print(table)

    def _edit_setting(self) -> None:
        print("\n[bold]Configuraciones editables:[/bold]")
        all_keys = []
        for keys in self.SETTINGS_CATEGORIES.values():
            all_keys.extend(keys)
        
        for i, key in enumerate(all_keys):
            value = getattr(settings, key, "N/A")
            if isinstance(value, list):
                display = json.dumps(value, ensure_ascii=False)
            else:
                display = str(value)
            if "KEY" in key.upper() or "PASSWORD" in key.upper() or "SECRET" in key.upper():
                display = "***MASKED***" if display != "" else "(vacío)"
            print(f"  [{i}] {key} = {display}")
        
        selection = prompt_input("Seleccione índice (Enter para cancelar)", default="")
        if not selection:
            return
        
        try:
            idx = int(selection)
            if idx < 0 or idx >= len(all_keys):
                print_error("Índice inválido")
                return
        except ValueError:
            print_error("Entrada inválida")
            return
        
        key = all_keys[idx]
        current = getattr(settings, key, None)
        
        if isinstance(current, list):
            current_display = json.dumps(current, ensure_ascii=False)
            print_info(f"Valor actual (JSON array): {current_display}")
            print_info("Ingrese nuevo valor como JSON array, ej: [\"host1\",\"host2\"]")
            new_value = prompt_input("Nuevo valor", default=current_display)
            try:
                parsed = json.loads(new_value)
                if not isinstance(parsed, list):
                    print_error("Debe ser un array JSON")
                    return
            except json.JSONDecodeError:
                print_error("JSON inválido")
                return
        elif isinstance(current, bool):
            print_info(f"Valor actual: {current}")
            new_value = prompt_input("Nuevo valor (true/false)", default=str(current).lower())
            if new_value.lower() not in ("true", "false"):
                print_error("Debe ser true o false")
                return
            parsed = new_value.lower() == "true"
        elif isinstance(current, int):
            print_info(f"Valor actual: {current}")
            new_value = prompt_input("Nuevo valor (entero)", default=str(current))
            try:
                parsed = int(new_value)
            except ValueError:
                print_error("Debe ser un número entero")
                return
        else:
            print_info(f"Valor actual: {current}")
            new_value = prompt_input("Nuevo valor", default=str(current) if current is not None else "")
            parsed = new_value

        if confirm_action(f"¿Guardar {key} = {parsed} en .env?"):
            self._write_env(key, parsed)
            print_success(f"✅ {key} actualizado. Reinicie la app para aplicar cambios.")

    def _write_env(self, key: str, value: Any) -> None:
        """Write a key-value pair to .env file"""
        env_lines = []
        if self.env_path.exists():
            with open(self.env_path, "r", encoding="utf-8") as f:
                env_lines = f.readlines()
        
        # Format value for .env
        if isinstance(value, list):
            env_value = json.dumps(value, ensure_ascii=False)
        elif isinstance(value, bool):
            env_value = str(value).lower()
        else:
            env_value = str(value)
        
        # Check if key exists
        key_found = False
        new_lines = []
        for line in env_lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                existing_key = stripped.split("=")[0].strip()
                if existing_key == key:
                    new_lines.append(f"{key}={env_value}\n")
                    key_found = True
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)
        
        if not key_found:
            new_lines.append(f"\n{key}={env_value}\n")
        
        self.env_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.env_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

    def _show_env_file(self) -> None:
        if not self.env_path.exists():
            print_warning("No existe archivo .env")
            return
        
        print(f"\n[bold]Contenido de {self.env_path}:[/bold]")
        with open(self.env_path, "r", encoding="utf-8") as f:
            content = f.read()
        print(content)

    def _create_env_example(self) -> None:
        example_path = Path(__file__).resolve().parents[2] / ".env.dev.example"
        if not example_path.exists():
            print_error("No se encuentra .env.dev.example")
            return
        
        if self.env_path.exists():
            if not confirm_action(f"El archivo {self.env_path} ya existe. ¿Sobrescribir?"):
                return
        
        with open(example_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        self.env_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.env_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        print_success(f"✅ .env creado desde ejemplo en {self.env_path}")


class CaptureTrafficCommand(CliCommand):
    """Start/stop traffic capture using ApiFlowRuntime"""

    def __init__(self, runtime=None):
        super().__init__("capture_traffic", "Captura de Tráfico")
        self.runtime = runtime or ApiFlowRuntime()
        self.console = Console()

    def execute(self, args: list[str] | None = None) -> int:
        try:
            clear_console()
            print_info("📡 Control de Captura de Tráfico")
            choice = prompt_input("Acción (start/stop/toggle/status) [status]", default="status")
            choice = choice.strip().lower()
            if choice == "start":
                self.runtime.start_capture()
                print_success("Captura iniciada")
            elif choice == "stop":
                self.runtime.stop_capture()
                print_success("Captura detenida (flush en background)")
            elif choice == "toggle":
                self.runtime.toggle_capture()
                print_info("Toggle ejecutado")
            else:
                state = self.runtime.snapshot_state()
                self.console.print(state_to_table(state))
            return 0
        except Exception as e:
            print_error(f"Error en control de captura: {e}")
            return 1


def state_to_table(state) -> Table:
    table = Table(title="Estado de Captura")
    table.add_column("Campo")
    table.add_column("Valor")
    table.add_row("Captura corriendo", str(state.capture_running))
    table.add_row("Estado captura", str(state.capture_status))
    table.add_row("Session ID", str(state.session_id))
    table.add_row("Host:Port", f"{state.session_host}:{state.session_port}")
    table.add_row("Eventos en vivo", str(state.live_event_count))
    table.add_row("Pendientes", str(state.pending_count))
    table.add_row("Descartados", str(state.dropped_pending_events))
    table.add_row("Flush fallidos", str(state.flush_failures))
    return table


class SystemMonitorCommand(CliCommand):
    """Monitor de recursos de proceso"""

    def __init__(self):
        super().__init__("system_monitor", "Monitor de Sistema")
        self.monitor = ProcessResourceMonitor()
        self.console = Console()

    def execute(self, args: list[str] | None = None) -> int:
        try:
            clear_console()
            print_info("📊 Monitor de Sistema")
            pid_input = prompt_input("PID a monitorear (\"self\" para proceso actual) [self]", default="self")
            if pid_input.strip().lower() in ("", "self"):
                pid = None
            else:
                try:
                    pid = int(pid_input)
                except ValueError:
                    print_error("PID inválido")
                    return 1

            if pid is None:
                pid = os.getpid()

            stats = self.monitor.read_usage(pid)
            self.console.print(self.monitor.format_usage(f"PID {pid}", stats))
            return 0
        except Exception as e:
            print_error(f"Error en monitor de sistema: {e}")
            return 1
