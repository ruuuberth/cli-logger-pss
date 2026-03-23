from __future__ import annotations

import os
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

    def read_usage(self, pid: int | None) -> ProcessUsage | None:
        if not pid:
            return None
        try:
            with open(f"/proc/{pid}/stat", "r", encoding="utf-8") as handle:
                stat_fields = handle.read().split()
            total_jiffies = float(stat_fields[13]) + float(stat_fields[14])
            rss_pages = float(stat_fields[23])
        except Exception:
            self._sample_cache.pop(pid, None)
            return None

        rss_mb = (rss_pages * os.sysconf("SC_PAGE_SIZE")) / (1024 * 1024)
        sample_time = time.monotonic()
        previous = self._sample_cache.get(pid)
        self._sample_cache[pid] = (sample_time, int(total_jiffies))

        cpu_percent = 0.0
        if previous is not None:
            prev_time, prev_jiffies = previous
            elapsed = sample_time - prev_time
            if elapsed > 0:
                ticks_per_second = float(os.sysconf("SC_CLK_TCK"))
                cpu_count = float(os.cpu_count() or 1)
                cpu_percent = max(
                    0.0,
                    ((total_jiffies - prev_jiffies) / ticks_per_second) / elapsed * 100.0 / cpu_count,
                )

        total_mem_pages = os.sysconf("SC_PHYS_PAGES")
        total_mem_mb = (total_mem_pages * os.sysconf("SC_PAGE_SIZE")) / (1024 * 1024)
        mem_percent = (rss_mb / total_mem_mb) * 100.0 if total_mem_mb > 0 else 0.0
        return ProcessUsage(cpu_percent=cpu_percent, rss_mb=rss_mb, mem_percent=mem_percent)

    def format_usage(self, label: str, stats: ProcessUsage | None) -> str:
        if not stats:
            return f"{label}: CPU -, RAM -"
        return (
            f"{label}: CPU {stats.cpu_percent:.1f}%"
            f", RAM {stats.rss_mb:.0f} MB ({stats.mem_percent:.1f}%)"
        )
