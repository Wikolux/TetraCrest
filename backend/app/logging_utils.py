import logging as std_logging
import sys
from datetime import datetime


class JsonFormatter(std_logging.Formatter):
    def format(self, record: std_logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        return self._serialize(log_entry)

    def _serialize(self, payload: dict) -> str:
        import json

        return json.dumps(payload, default=str)


def get_logger(name: str) -> std_logging.Logger:
    logger = std_logging.getLogger(name)
    if logger.handlers:
        return logger

    handler = std_logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(std_logging.INFO)
    logger.propagate = False
    return logger
