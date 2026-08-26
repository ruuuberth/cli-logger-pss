"""CLI Utilities for Logger-PSS"""
from __future__ import annotations

import os
from typing import Optional
from rich.console import Console
from rich.prompt import Prompt, Confirm


# Emoji to ASCII mapping for fallback
_EMOJI_MAP = {
    "✅": "[OK]",
    "❌": "[ERROR]",
    "⚠️": "[WARN]",
    "ℹ️": "[INFO]",
    "🔍": "[SEARCH]",
    "📋": "[REPORT]",
    "👤": "[USER]",
    "🏠": "[ROOM]",
    "🎖️": "[BATTLE]",
    "📡": "[CAPTURE]",
    "📊": "[MONITOR]",
    "⚙️": "[CONFIG]",
    "✨": "[START]",
    "⏸️": "[PAUSE]",
}


def _to_ascii(text: str) -> str:
    """Replace emojis with ASCII equivalents."""
    for emoji, ascii_repr in _EMOJI_MAP.items():
        text = text.replace(emoji, ascii_repr)
    return text


def _safe_print(console: Console, message: str, style: str = "") -> None:
    """Print with automatic ASCII fallback if Unicode fails."""
    try:
        console.print(message, style=style)
    except UnicodeEncodeError:
        console.print(_to_ascii(message), style=style)


def clear_console() -> None:
    """Clear the terminal screen based on OS"""
    os.system('cls' if os.name == 'nt' else 'clear')


def print_info(message: str, console: Optional[Console] = None) -> None:
    """Print info message"""
    c = console or Console()
    _safe_print(c, f"[cyan]ℹ️ {message}[/cyan]")


def print_success(message: str, console: Optional[Console] = None) -> None:
    """Print success message"""
    c = console or Console()
    _safe_print(c, f"[green]✅ {message}[/green]")


def print_error(message: str, console: Optional[Console] = None) -> None:
    """Print error message"""
    c = console or Console()
    _safe_print(c, f"[red]❌ {message}[/red]")


def print_warning(message: str, console: Optional[Console] = None) -> None:
    """Print warning message"""
    c = console or Console()
    _safe_print(c, f"[yellow]⚠️ {message}[/yellow]")


def confirm_action(message: str, console: Optional[Console] = None) -> bool:
    """Ask for confirmation"""
    c = console or Console()
    return Confirm.ask(message, console=c)


def prompt_input(message: str, console: Optional[Console] = None, default: str = "") -> str:
    """Prompt for user input"""
    c = console or Console()
    return Prompt.ask(message, console=c, default=default if default else None)
