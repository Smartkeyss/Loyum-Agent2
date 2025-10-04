from __future__ import annotations

import logging
from contextlib import contextmanager
from time import perf_counter
from typing import Any, Dict, Iterator


def configure_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


@contextmanager
def log_external_call(logger: logging.Logger, *, context: str, payload: Dict[str, Any] | None = None) -> Iterator[None]:
    start = perf_counter()
    logger.debug("Starting external call", extra={"context": context, "payload": _redact_sensitive(payload)})
    try:
        yield
    finally:
        duration = perf_counter() - start
        logger.info("Completed external call", extra={"context": context, "duration_sec": round(duration, 3)})


def _redact_sensitive(payload: Dict[str, Any] | None) -> Dict[str, Any] | None:
    if payload is None:
        return None
    redacted: Dict[str, Any] = {}
    for key, value in payload.items():
        if "token" in key.lower() or "key" in key.lower():
            redacted[key] = "***REDACTED***"
        else:
            redacted[key] = value
    return redacted