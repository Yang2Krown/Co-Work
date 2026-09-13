"""Structured logging helpers for RAG requests."""

import json
import logging
import sys
from typing import Any, Dict, Optional, TextIO


class StructuredJSONFormatter(logging.Formatter):
    """Render RAG event payloads as one JSON object per log line."""

    def format(self, record: logging.LogRecord) -> str:
        event = getattr(record, "rag_event", None)
        if isinstance(event, dict):
            return json.dumps(event, ensure_ascii=False, sort_keys=True)
        return super().format(record)


def configure_structured_logging(
    logger: Optional[logging.Logger] = None,
    level: int = logging.INFO,
    stream: Optional[TextIO] = None,
) -> logging.Logger:
    """Attach a JSON handler to a logger without exposing credentials."""

    target = logger or logging.getLogger("backend.rag")
    target.setLevel(level)
    target.propagate = False
    if not target.handlers:
        handler = logging.StreamHandler(stream or sys.stderr)
        handler.setFormatter(StructuredJSONFormatter())
        target.addHandler(handler)
    return target


def log_rag_request(logger: logging.Logger, event: Dict[str, Any]) -> None:
    """Write one structured request event."""

    logger.info("rag_request", extra={"rag_event": event})


__all__ = ["StructuredJSONFormatter", "configure_structured_logging", "log_rag_request"]
