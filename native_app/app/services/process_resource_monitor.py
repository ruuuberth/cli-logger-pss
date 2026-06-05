from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class ProcessUsage:
    cpu_percent: float
    rss_mb: float
    mem_percent: float


class ProcessResourceMonitor:
    def __init__(self) -> None:
        self._sample_cache: dict[int, tuple[float, int]] = {}
        self._use_psutil = self._check_psutil_available()

    def _check_psutil_available(self) -> bool:
        """Verificar si psutil está disponible para Windows/Linux alternativo"""
        try:
            import psutil
            return True
        except ImportError:
            return False

    def read_usage(self, pid: int | None) -> ProcessUsage | None:
        if not pid:
            return None
        
        # Usar psutil si está disponible (preferido para Windows)
        if self._use_psutil:
            return self._read_usage_psutil(pid)
        
        # Fallback a /proc para Linux
        if sys.platform == "linux":
            return self._read_usage_proc(pid)
        
        # Windows sin psutil - retornar None (no soportado)
        return None

    def _read_usage_psutil(self, pid: int) -> ProcessUsage | None:
        """Leer uso de recursos usando psutil (funciona en Windows y Linux)"""
        try:
            import psutil
            try:
                process = psutil.Process(pid)
                cpu_percent = process.cpu_percent(interval=None)
                mem_info = process.memory_info()
                rss_mb = mem_info.rss / (1024 * 1024)
                mem_percent = process.memory_percent()
                return ProcessUsage(
                    cpu_percent=cpu_percent,
                    rss_mb=rss_mb,
                    mem_percent=mem_percent,
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                self._sample_cache.pop(pid, None)
                return None
        except Exception:
            return None

    def _read_usage_proc(self, pid: int) -> ProcessUsage | None:
        """Leer uso de recursos desde /proc (solo Linux)"""
        try:
            with open(f"/proc/{pid}/stat", "r", encoding="utf-8") as handle:
                stat_fields = handle.read().split()
            total_jiffies = float(stat_fields[13]) + float(stat_fields[14])
            rss_pages = float(stat_fields[23])
        except Exception:
            self._sample_cache.pop(pid, None)
            return None

        try:
            rss_mb = (rss_pages * os.sysconf("SC_PAGE_SIZE")) / (1024 * 1024)
        except (ValueError, OSError):
            rss_mb = 0.0
        
        sample_time = time.monotonic()
        previous = self._sample_cache.get(pid)
        self._sample_cache[pid] = (sample_time, int(total_jiffies))

        cpu_percent = 0.0
        if previous is not None:
            prev_time, prev_jiffies = previous
            elapsed = sample_time - prev_time
            if elapsed > 0:
                try:
                    ticks_per_second = float(os.sysconf("SC_CLK_TCK"))
                    cpu_count = float(os.cpu_count() or 1)
                    cpu_percent = max(
                        0.0,
                        ((total_jiffies - prev_jiffies) / ticks_per_second) / elapsed * 100.0 / cpu_count,
                    )
                except (ValueError, OSError):
                    cpu_percent = 0.0

        try:
            total_mem_pages = os.sysconf("SC_PHYS_PAGES")
            total_mem_mb = (total_mem_pages * os.sysconf("SC_PAGE_SIZE")) / (1024 * 1024)
            mem_percent = (rss_mb / total_mem_mb) * 100.0 if total_mem_mb > 0 else 0.0
        except (ValueError, OSError):
            mem_percent = 0.0
        return ProcessUsage(cpu_percent=cpu_percent, rss_mb=rss_mb, mem_percent=mem_percent)

    def format_usage(self, label: str, stats: ProcessUsage | None) -> str:
        if not stats:
            return f"{label}: CPU -, RAM -"
        return (
            f"{label}: CPU {stats.cpu_percent:.1f}%"
            f", RAM {stats.rss_mb:.0f} MB ({stats.mem_percent:.1f}%)"
        )
