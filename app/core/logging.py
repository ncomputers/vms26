import json
import logging
from datetime import datetime
from typing import Optional


class JsonFormatter(logging.Formatter):
    """Log formatter that outputs JSON with specific fields."""

    def format(self, record: logging.LogRecord) -> str:  # pragma: no cover - trivial
        log_record = {
            "ts": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "name": record.name,
            "msg": record.getMessage(),
        }
        if "camera_id" in record.__dict__ and record.__dict__["camera_id"] is not None:
            log_record["camera_id"] = record.__dict__["camera_id"]
        if "stage" in record.__dict__ and record.__dict__["stage"] is not None:
            log_record["stage"] = record.__dict__["stage"]
        if record.exc_info:
            log_record["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(log_record)


def setup_json_logger(name: str = "vms21", level: str = "INFO") -> logging.Logger:
    """Configure and return a logger with JSON output to stdout."""
    logger = logging.getLogger(name)
    if logger.handlers:  # Already configured
        return logger
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def log_ex(
    logger: logging.Logger,
    stage: str,
    camera_id: Optional[str],
    msg: str,
    **kwargs,
):
    """Log a message with stage and camera information."""
    return logger.info(msg, extra={"stage": stage, "camera_id": camera_id, **kwargs})
