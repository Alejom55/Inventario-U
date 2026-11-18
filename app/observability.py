"""Bounded correlation IDs and JSON application logs without request credentials."""

from datetime import datetime, timezone
import json
import logging
import os
import re
from uuid import uuid4


def correlation_id(value):
    return value if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value) else str(uuid4())


class JsonFormatter(logging.Formatter):
    def format(self, record):
        data = {
            "timestamp_utc": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname, "logger": record.name, "message": record.getMessage(),
            "round": round_identity(),
            "execution_id": execution_identity(),
        }
        for field in ("trace_id", "service", "path", "status", "duration_ms", "round", "event", "outcome",
                      "control", "reason", "decision", "actor", "credential_ref", "execution_id"):
            if hasattr(record, field):
                data[field] = getattr(record, field)
        return json.dumps(data, ensure_ascii=True)


def configure_logging():
    logger = logging.getLogger("app")
    if not any(isinstance(handler.formatter, JsonFormatter) for handler in logger.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def round_identity():
    value = os.getenv("CHAOS_ROUND", "none")
    return value if value in {"BASELINE", "R0", "R1"} else "none"


def execution_identity():
    value = os.getenv("CHAOS_EXECUTION_ID", "none")
    return value if re.fullmatch(r"[a-f0-9]{32}", value) else "none"
