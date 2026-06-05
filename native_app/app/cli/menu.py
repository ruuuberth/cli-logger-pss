"""CLI Menu system with Rich terminal UI"""
from __future__ import annotations

from typing import Callable, Optional, Any
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from app.cli.utils import clear_console


class MenuItem:
    """Represents a menu item"""

    def __init__(
        self,
        key: str,
        label: str,
        handler: Optional[Callable[[], Any]] = None,
        submenu: Optional["Menu"] = None,
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
        console: Optional[Console] = None,
    ):
        self.title = title
        self.items: list[MenuItem] = []
        self.console = console or Console()

    def add_item(
        self,
        key: str,
        label: str,
        handler: Optional[Callable[[], Any]] = None,
        submenu: Optional[Menu] = None,
    ) -> None:
        """Add an item to the menu"""
        if handler and submenu:
            raise ValueError("Cannot set both handler and submenu")
        self.items.append(MenuItem(key, label, handler, submenu))

    def show(self) -> Optional[str]:
        """Display menu and return selected key, or None if exit"""
        clear_console()
        
        # Render title
        self.console.print(Panel(self.title, style="bold cyan", expand=True))
        
        # Render menu items
        for item in self.items:
            self.console.print(f"  [{item.key}] {item.label}")
        
        self.console.print(f"  [q] Salir")
        self.console.print()
        
        # Get user input
        from rich.prompt import Prompt
        choice = Prompt.ask("Selecciona una opción", console=self.console).strip().lower()
        
        if choice == "q":
            return None
        
        for item in self.items:
            if item.key.lower() == choice:
                return item.key
        
        self.console.print("[red]❌ Opción no válida[/red]")
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
                        self.console.print("[yellow]\\n⏸️  Cancelado[/yellow]")
                    except Exception as e:
                        self.console.print(f"[red]❌ Error: {e}[/red]")
                    finally:
                        if not item.submenu:
                            self.console.print("\n[dim]Presiona Enter para continuar...[/dim]")
                            self.console.input()
                    break


class Table:
    """Simple table for displaying data"""
    
    @staticmethod
    def create(title: str, columns: list[str]) -> "Table":
        """Create a table with Rich"""
        table = Table(title=title, box=box.ROUNDED, show_header=True, header_style="bold cyan")
        for col in columns:
            table.add_column(col)
        return table
