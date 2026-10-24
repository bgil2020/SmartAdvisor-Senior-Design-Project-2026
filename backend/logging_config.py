
import json
import logging
import sys
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    def format(self, record):
        data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "event": getattr(record, "event", "api_request"),
            "method": getattr(record, "method", None),
            "endpoint": getattr(record, "endpoint", None),
            "status_code": getattr(record, "status_code", None),
            "error_category": getattr(record, "error_category", None),
        }
        return json.dumps(data)


def get_api_logger():
    logger = logging.getLogger("smartadvisor.api")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)

    return logger
