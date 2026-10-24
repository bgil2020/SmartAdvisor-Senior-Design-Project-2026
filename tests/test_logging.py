
import json
import logging

from fastapi.testclient import TestClient

from backend.api import app
from backend.logging_config import get_api_logger


client = TestClient(app)


class LogCapture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(json.loads(self.format(record)))


def capture_api_logs():
    logger = get_api_logger()
    handler = LogCapture()
    handler.setFormatter(logger.handlers[0].formatter)
    logger.addHandler(handler)
    return logger, handler


def test_successful_request_logging():
    logger, handler = capture_api_logs()

    try:
        response = client.get("/courses")
        assert response.status_code == 200

        logs = [
            entry
            for entry in handler.records
            if entry["endpoint"] == "/courses"
        ]

        assert logs
        assert logs[-1]["method"] == "GET"
        assert logs[-1]["status_code"] == 200
        assert logs[-1]["error_category"] is None
    finally:
        logger.removeHandler(handler)


def test_validation_error_logging():
    logger, handler = capture_api_logs()

    try:
        response = client.get("/alternatives")
        assert response.status_code == 422

        logs = [
            entry
            for entry in handler.records
            if entry["endpoint"] == "/alternatives"
        ]

        assert logs
        assert logs[-1]["status_code"] == 422
        assert logs[-1]["error_category"] == "CLIENT_ERROR"
    finally:
        logger.removeHandler(handler)


def test_sensitive_query_not_logged():
    logger, handler = capture_api_logs()

    try:
        secret = "PRIVATE_TEST_TOKEN_12345"

        response = client.get(
            "/courses",
            params={"secret": secret},
        )

        assert response.status_code == 200

        serialized_logs = json.dumps(handler.records)

        assert secret not in serialized_logs
        assert "secret" not in serialized_logs
    finally:
        logger.removeHandler(handler)
