"""Command base class and decorator for CLI commands"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Optional


class CliCommand(ABC):
    """Base class for CLI commands"""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    @abstractmethod
    def execute(self, args: list[str] = None) -> int:
        """Execute the command. Return 0 for success, non-zero for error."""
        pass


class CommandRegistry:
    """Registry for CLI commands"""

    _commands: dict[str, CliCommand] = {}

    @classmethod
    def register(cls, command: CliCommand) -> None:
        """Register a command"""
        cls._commands[command.name] = command

    @classmethod
    def get(cls, name: str) -> Optional[CliCommand]:
        """Get a command by name"""
        return cls._commands.get(name)

    @classmethod
    def list_all(cls) -> dict[str, CliCommand]:
        """List all registered commands"""
        return dict(cls._commands)


def command(name: str, description: str) -> Callable:
    """Decorator for registering commands"""
    def decorator(cls: type[CliCommand]) -> type[CliCommand]:
        instance = cls(name, description)
        CommandRegistry.register(instance)
        return cls
    return decorator
