"""Lightweight stage timing for request observability."""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Any, Iterator

logger = logging.getLogger("rag_api.timing")


class StageTimer:
    """Accumulate stage durations and emit a summary log line."""

    def __init__(self, label: str, **meta: Any) -> None:
        self.label = label
        self.meta = {k: v for k, v in meta.items() if v is not None}
        self._t0 = time.perf_counter()
        self._last = self._t0
        self.stages: list[tuple[str, float]] = []

    def mark(self, stage: str, **extra: Any) -> float:
        now = time.perf_counter()
        ms = (now - self._last) * 1000.0
        self._last = now
        self.stages.append((stage, ms))
        fields = {**self.meta, **extra, "stage_ms": f"{ms:.1f}"}
        logger.info(
            "timing %s stage=%s %s",
            self.label,
            stage,
            _fmt(fields),
        )
        return ms

    def finish(self, **extra: Any) -> float:
        total_ms = (time.perf_counter() - self._t0) * 1000.0
        breakdown = " ".join(f"{name}={ms:.1f}ms" for name, ms in self.stages)
        fields = {
            **self.meta,
            **extra,
            "total_ms": f"{total_ms:.1f}",
            "breakdown": breakdown or "-",
        }
        logger.info("timing %s done %s", self.label, _fmt(fields))
        return total_ms


@contextmanager
def timed(label: str, **meta: Any) -> Iterator[None]:
    t0 = time.perf_counter()
    try:
        yield
    finally:
        ms = (time.perf_counter() - t0) * 1000.0
        fields = {**meta, "elapsed_ms": f"{ms:.1f}"}
        logger.info("timing %s %s", label, _fmt(fields))


def _fmt(fields: dict[str, Any]) -> str:
    return " ".join(f"{k}={v}" for k, v in fields.items())
