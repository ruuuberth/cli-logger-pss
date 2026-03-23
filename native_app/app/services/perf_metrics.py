from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Iterator


@contextmanager
def measure_perf(
    name: str,
    logger: logging.Logger,
    threshold_ms: int = 50,
) -> Iterator[None]:
    started = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        if elapsed_ms >= float(threshold_ms):
            logger.info("event=perf_metric name=%s elapsed_ms=%.2f", name, elapsed_ms)
