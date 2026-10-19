"""CLI Menu system with Rich terminal UI"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from app.cli.utils import _safe_print, clear_console


class MenuItem:
    """Represents a menu item"""

    def __init__(
        self,
        key: str,
        label: str,
        handler: Callable[[], Any] | None = None,
        submenu: Menu | None = None,
    ):
        self.key = key
        self.label = label
        self.handler = handler
        self.submenu = submenu


class Menu:
    """Interactive menu system using Rich"""

    def __init__(
        self,
        title: str,
        console: Console | None = None,
    ):
        self.title = title
        self.items: list[MenuItem] = []
        self.console = console or Console()

    def add_item(
        self,
        key: str,
        label: str,
        handler: Callable[[], Any] | None = None,
        submenu: Menu | None = None,
    ) -> None:
        """Add an item to the menu"""
        if handler and submenu:
            raise ValueError("Cannot set both handler and submenu")
        self.items.append(MenuItem(key, label, handler, submenu))

    def show(self) -> str | None:
        """Display menu and return selected key, or None if exit"""
        clear_console()

        # Render title
        self.console.print(Panel(self.title, style="bold cyan", expand=True))

        # Render menu items
        for item in self.items:
            self.console.print(f"  [{item.key}] {item.label}")

        self.console.print("  [q] Salir")
        self.console.print()

        # Get user input
        from rich.prompt import Prompt

        choice = (
            Prompt.ask("Selecciona una opción", console=self.console).strip().lower()
        )

        if choice == "q":
            return None

        for item in self.items:
            if item.key.lower() == choice:
                return item.key

        _safe_print(self.console, "[red]❌ Opción no válida[/red]")
        self.console.print("\n[dim]Presiona Enter para continuar...[/dim]")
        self.console.input()
        return self.show()

    def run(self) -> None:
        """Run the menu loop"""
        while True:
            selected = self.show()

            if selected is None:
                break

            for item in self.items:
                if item.key == selected:
                    try:
                        if item.submenu:
                            item.submenu.run()
                        elif item.handler:
                            item.handler()
                    except KeyboardInterrupt:
                        _safe_print(self.console, "[yellow]\\n⏸️  Cancelado[/yellow]")
                    except Exception as e:
                        _safe_print(self.console, f"[red]❌ Error: {e}[/red]")
                    finally:
                        if not item.submenu:
                            self.console.print(
                                "\n[dim]Presiona Enter para continuar...[/dim]"
                            )
                            self.console.input()
                    break


class MenuTable:
    """Simple table for displaying data"""

    @staticmethod
    def create(title: str, columns: list[str]) -> MenuTable:
        """Create a table with Rich"""
        table = Table(
            title=title, box=box.ROUNDED, show_header=True, header_style="bold cyan"
        )
        for col in columns:
            table.add_column(col)
        return table
