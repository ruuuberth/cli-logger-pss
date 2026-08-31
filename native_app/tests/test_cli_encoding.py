"""Tests for encoding and ASCII fallback in CLI."""

import io
from rich.console import Console

from app.cli.utils import (
    print_info, print_success, print_error, print_warning, _to_ascii, _safe_print
)
from app.cli.cli_manager import _create_console


class TestCliEncoding:
    """Tests for encoding helpers and fallback ASCII."""

    def test_to_ascii_replaces_common_emojis(self) -> None:
        text = "✅ Success ❌ Error ⚠️ Warning ℹ️ Info"
        result = _to_ascii(text)
        assert "[OK]" in result
        assert "[ERROR]" in result
        assert "[WARN]" in result
        assert "[INFO]" in result
        assert "✅" not in result
        assert "❌" not in result
        assert "⚠️" not in result
        assert "ℹ️" not in result

    def test_to_ascii_replaces_all_known_emojis(self) -> None:
        text = "🔍 📋 👤 🏠 🎖️ 📡 📊 ⚙️ ✨ ⏸️"
        result = _to_ascii(text)
        assert "[SEARCH]" in result
        assert "[REPORT]" in result
        assert "[USER]" in result
        assert "[ROOM]" in result
        assert "[BATTLE]" in result
        assert "[CAPTURE]" in result
        assert "[MONITOR]" in result
        assert "[CONFIG]" in result
        assert "[START]" in result
        assert "[PAUSE]" in result

    def test_to_ascii_leaves_unknown_text_unchanged(self) -> None:
        text = "Hello World 123"
        result = _to_ascii(text)
        assert result == "Hello World 123"

    def test_safe_print_no_error_on_ascii_console(self) -> None:
        """_safe_print should not raise UnicodeEncodeError on ASCII-only console."""
        console = Console(file=io.StringIO(), force_terminal=True, legacy_windows=True)
        _safe_print(console, "✅ Test message")  # Should not raise

    def test_safe_print_uses_ascii_fallback_when_needed(self) -> None:
        """_safe_print should fall back to ASCII when Unicode fails."""
        console = Console(file=io.StringIO(), force_terminal=True, legacy_windows=True)
        
        # Mock console.print to raise UnicodeEncodeError on first call, succeed on second
        original_print = console.print
        call_count = [0]
        
        def mock_print(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise UnicodeEncodeError("ascii", "✅", 0, 1, "ordinal not in range(128)")
            return original_print(*args, **kwargs)
        
        console.print = mock_print
        _safe_print(console, "✅ Test message")
        # If we get here without exception, fallback worked
        assert True

    def test_safe_print_works_normally_on_utf8_console(self) -> None:
        """_safe_print should work normally on UTF-8 console."""
        console = Console(file=io.StringIO(), force_terminal=True, legacy_windows=False)
        _safe_print(console, "✅ Test message")
        # Should not raise, test passes if no exception

    def test_create_console_returns_console_instance(self) -> None:
        """_create_console should return a Console instance."""
        console = _create_console(force_ascii=True)
        assert isinstance(console, Console)
        
        console = _create_console(force_ascii=False)
        assert isinstance(console, Console)

    def test_create_console_force_terminal_true(self) -> None:
        """_create_console should always set force_terminal=True."""
        console = _create_console(force_ascii=True)
        # Test behavior: console should be a proper Console instance
        # force_terminal is a private attribute, test behavior instead
        assert isinstance(console, Console)
        assert console.is_terminal or console._force_terminal is True
        
        console = _create_console(force_ascii=False)
        assert isinstance(console, Console)
        assert console.is_terminal or console._force_terminal is True


class TestPrintHelpers:
    """Tests for print_info, print_success, etc. with fallback."""

    def test_print_info_doesnt_crash_on_ascii_console(self) -> None:
        console = Console(file=io.StringIO(), force_terminal=True, legacy_windows=True)
        print_info("test message", console=console)

    def test_print_success_doesnt_crash_on_ascii_console(self) -> None:
        console = Console(file=io.StringIO(), force_terminal=True, legacy_windows=True)
        print_success("test message", console=console)

    def test_print_error_doesnt_crash_on_ascii_console(self) -> None:
        console = Console(file=io.StringIO(), force_terminal=True, legacy_windows=True)
        print_error("test message", console=console)

    def test_print_warning_doesnt_crash_on_ascii_console(self) -> None:
        console = Console(file=io.StringIO(), force_terminal=True, legacy_windows=True)
        print_warning("test message", console=console)

    def test_print_helpers_work_on_utf8_console(self) -> None:
        console = Console(file=io.StringIO(), force_terminal=True, legacy_windows=False)
        print_info("test", console=console)
        print_success("test", console=console)
        print_error("test", console=console)
        print_warning("test", console=console)