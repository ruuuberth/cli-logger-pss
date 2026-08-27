from __future__ import annotations

import functools
import logging
import time
from contextlib import contextmanager
from typing import Any, Callable, Iterator


def profile_method(threshold_ms: int = 50):
    def decorator(func: Callable[..., Any]):
        logger = logging.getLogger(func.__module__)

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            started = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                elapsed_ms = (time.perf_counter() - started) * 1000.0
                if elapsed_ms >= float(threshold_ms):
                    logger.info("event=perf_metric func=%s elapsed_ms=%.2f", func.__name__, elapsed_ms)
        return wrapper
    return decorator


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
