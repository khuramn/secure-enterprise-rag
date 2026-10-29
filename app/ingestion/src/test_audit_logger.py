import json
import os
import uuid
from unittest.mock import patch

from audit_logger import audit_event, logger


TEST_KEY = "ci-only-audit-hmac-key-not-for-production-123456"


class CaptureHandler:
    def __init__(self):
        self.records = []

    def emit(self, record):
        self.records.append(record)


def capture_event(**kwargs):
    records = []

    with patch.dict(os.environ, {"RAG_AUDIT_HMAC_KEY": TEST_KEY}):
        with patch.object(logger, "info") as mock_info:
            audit_event(**kwargs)

    assert mock_info.call_count == 1
    return json.loads(mock_info.call_args.args[0])


def base_event():
    return {
        "event_type": "rag.retrieval.completed",
        "request_id": str(uuid.uuid4()),
        "username": "alice@example.com",
        "outcome": "success",
        "document_ids": ["FIN-001"],
        "document_count": 1,
    }


def test_pseudonymisation():
    event = capture_event(**base_event())

    assert event["username"].startswith("hmac-sha256:")
    assert "alice@example.com" not in json.dumps(event)
    assert event["document_ids"] == ["FIN-001"]

    print("PASS: Username pseudonymised")


def test_consistent_subject():
    first = capture_event(**base_event())
    second = capture_event(**base_event())

    assert first["username"] == second["username"]

    print("PASS: Consistent audit subject identifier")


def test_invalid_reason():
    event = base_event()
    event["reason"] = "SECRET_INTERNAL_PASSWORD"

    with patch.dict(os.environ, {"RAG_AUDIT_HMAC_KEY": TEST_KEY}):
        with patch.object(logger, "info") as mock_info:
            try:
                audit_event(**event)
            except ValueError:
                pass
            else:
                raise AssertionError("Unsafe reason was accepted")

            mock_info.assert_not_called()

    print("PASS: Unsafe reason rejected")


def test_invalid_document_id():
    event = base_event()
    event["document_ids"] = ["FIN-001\nSECRET_TOKEN"]

    with patch.dict(os.environ, {"RAG_AUDIT_HMAC_KEY": TEST_KEY}):
        with patch.object(logger, "info") as mock_info:
            try:
                audit_event(**event)
            except ValueError:
                pass
            else:
                raise AssertionError("Unsafe document ID was accepted")

            mock_info.assert_not_called()

    print("PASS: Unsafe document ID rejected")


def test_invalid_request_id():
    event = base_event()
    event["request_id"] = "SECRET_INVALID_REQUEST_ID"

    with patch.dict(os.environ, {"RAG_AUDIT_HMAC_KEY": TEST_KEY}):
        with patch.object(logger, "info") as mock_info:
            try:
                audit_event(**event)
            except ValueError:
                pass
            else:
                raise AssertionError("Unsafe request ID was accepted")

            mock_info.assert_not_called()

    print("PASS: Invalid correlation ID rejected")


def test_missing_hmac_key():
    event = base_event()

    with patch.dict(os.environ, {}, clear=True):
        with patch.object(logger, "info") as mock_info:
            try:
                audit_event(**event)
            except RuntimeError:
                pass
            else:
                raise AssertionError("Missing HMAC key was accepted")

            mock_info.assert_not_called()

    print("PASS: Missing HMAC key fails closed")


if __name__ == "__main__":
    test_pseudonymisation()
    test_consistent_subject()
    test_invalid_reason()
    test_invalid_document_id()
    test_invalid_request_id()
    test_missing_hmac_key()

    print("\nAll audit logger security tests passed.")
