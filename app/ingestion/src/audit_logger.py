import hashlib
import hmac
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path


LOG_PATH = Path(
    os.getenv(
        "RAG_AUDIT_LOG_PATH",
        str(
            Path(__file__).resolve().parent.parent
            / "logs"
            / "security_audit.jsonl"
        ),
    )
)

ALLOWED_EVENTS = {
    "rag.authorization.denied",
    "rag.retrieval.completed",
    "rag.response.completed",
    "rag.content_filter.triggered",
    "api.authentication.denied",
    "api.authorization.denied",
    "api.query.failed",
    "api.request.failed",
}

ALLOWED_OUTCOMES = {
    "success",
    "denied",
    "blocked",
    "error",
    "insufficient_information",
}

ALLOWED_REASONS = {
    "unknown_identity",
    "authentication_failed",
    "claims_policy",
    "invalid_token",
    "pipeline_failure",
    "server_error",
}

DOCUMENT_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

logger = logging.getLogger("secure_rag.audit")
logger.setLevel(logging.INFO)
logger.propagate = False
azure_audit_logger = logging.getLogger("secure_rag.azure_audit")
azure_audit_logger.setLevel(logging.INFO)

LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

if not logger.handlers:
    handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)


def pseudonymise_subject(username: str) -> str:
    if username == "anonymous":
        return "anonymous"

    if not isinstance(username, str) or not username:
        raise ValueError("Invalid audit subject")

    key = os.getenv("RAG_AUDIT_HMAC_KEY")

    if not key or len(key.encode("utf-8")) < 32:
        raise RuntimeError(
            "RAG_AUDIT_HMAC_KEY must contain at least 32 bytes"
        )

    digest = hmac.new(
        key.encode("utf-8"),
        username.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return f"hmac-sha256:{digest}"


def audit_event(
    event_type: str,
    request_id: str,
    username: str,
    outcome: str,
    document_ids=None,
    **details,
):
    if event_type not in ALLOWED_EVENTS:
        raise ValueError("Invalid audit event type")

    if outcome not in ALLOWED_OUTCOMES:
        raise ValueError("Invalid audit outcome")

    try:
        validated_request_id = str(uuid.UUID(request_id))
    except (ValueError, AttributeError, TypeError) as exc:
        raise ValueError("Invalid audit request ID") from exc

    if document_ids is None:
        validated_document_ids = []
    elif (
        isinstance(document_ids, (list, tuple))
        and len(document_ids) <= 100
        and all(
            isinstance(doc_id, str)
            and DOCUMENT_ID_PATTERN.fullmatch(doc_id)
            for doc_id in document_ids
        )
    ):
        validated_document_ids = list(document_ids)
    else:
        raise ValueError("Invalid audit document IDs")

    safe_details = {}

    if "reason" in details:
        reason = details["reason"]
        if reason not in ALLOWED_REASONS:
            raise ValueError("Invalid audit reason")
        safe_details["reason"] = reason

    if "document_count" in details:
        count = details["document_count"]
        if (
            type(count) is not int
            or count < 0
            or count > 100000
        ):
            raise ValueError("Invalid audit document count")
        safe_details["document_count"] = count

    if "content_filter_triggered" in details:
        triggered = details["content_filter_triggered"]
        if type(triggered) is not bool:
            raise ValueError("Invalid content-filter flag")
        safe_details["content_filter_triggered"] = triggered

    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "request_id": validated_request_id,
        "username": pseudonymise_subject(username),
        "outcome": outcome,
        "document_ids": validated_document_ids,
        **safe_details,
    }

    validated_event_json = json.dumps(event, ensure_ascii=False)

    # Preserve the existing local audit trail.
    logger.info(validated_event_json)

    # Forward only the validated, pseudonymised event to Azure.
    # Never allow an Azure logging failure to interrupt the request.
    if os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"):
        try:
            azure_audit_logger.info(validated_event_json)
        except Exception:
            pass