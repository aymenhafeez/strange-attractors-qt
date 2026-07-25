import logging
import os
import time
from contextlib import contextmanager

PROFILE_ENV = "ATTRACTOR_PROFILE"
LOGGER_NAME = "attractors.perf"


def profiling_enabled():
    return os.environ.get(PROFILE_ENV, "").lower() in {"1", "true", "yes", "on"}


class PerfProfiler:
    def __init__(self, enabled=None, logger=None, clock=None):
        self.enabled = profiling_enabled() if enabled is None else enabled
        self._logger = logger or logging.getLogger(LOGGER_NAME)
        self._clock = clock or time.perf_counter
        self._starts = {}

    def start(self, name, key=None, **fields):
        if not self.enabled:
            return None

        token = (name, key if key is not None else id(fields))
        self._starts[token] = (self._clock(), fields)
        return token

    def finish(self, token, **fields):
        if not self.enabled or token is None:
            return None

        started = self._starts.pop(token, None)
        if started is None:
            return None

        start, start_fields = started
        elapsed_ms = (self._clock() - start) * 1000.0
        payload = {**start_fields, **fields}
        self._logger.info(
            "%s completed in %.1f ms%s",
            token[0],
            elapsed_ms,
            _format_fields(payload),
        )
        return elapsed_ms

    @contextmanager
    def measure(self, name, **fields):
        token = self.start(name, **fields)
        try:
            yield
        finally:
            self.finish(token)


def _format_fields(fields):
    if not fields:
        return ""

    formatted = " ".join(f"{key}={value}" for key, value in sorted(fields.items()))
    return f" ({formatted})"


def configure_perf_logging():
    if not profiling_enabled():
        return False

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    )
    logging.getLogger(LOGGER_NAME).setLevel(logging.INFO)
    return True


def perf_start(owner, name, key=None, **fields):
    profiler = getattr(owner, "_perf", None)
    if profiler is None:
        return None
    return profiler.start(name, key=key, **fields)


def perf_finish(owner, token, **fields):
    profiler = getattr(owner, "_perf", None)
    if profiler is None:
        return None
    return profiler.finish(token, **fields)
