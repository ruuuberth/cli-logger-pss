from __future__ import annotations

import os

from app.services.process_resource_monitor import ProcessResourceMonitor, ProcessUsage


def test_read_usage_none_returns_none() -> None:
    monitor = ProcessResourceMonitor()
    assert monitor.read_usage(None) is None


def test_read_usage_invalid_pid_returns_none() -> None:
    monitor = ProcessResourceMonitor()
    assert monitor.read_usage(999999999) is None


def test_format_usage_returns_fallback_for_missing_stats() -> None:
    monitor = ProcessResourceMonitor()
    assert monitor.format_usage("App", None) == "App: CPU -, RAM -"


def test_format_usage_renders_values() -> None:
    monitor = ProcessResourceMonitor()
    stats = ProcessUsage(cpu_percent=12.3, rss_mb=456.7, mem_percent=8.9)
    assert monitor.format_usage("App", stats) == "App: CPU 12.3%, RAM 457 MB (8.9%)"


def test_read_usage_current_process_returns_sample() -> None:
    monitor = ProcessResourceMonitor()
    first = monitor.read_usage(os.getpid())
    second = monitor.read_usage(os.getpid())
    assert first is not None
    assert second is not None
    assert second.rss_mb >= 0
