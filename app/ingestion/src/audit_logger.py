
import json
import logging
import os
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

logger = logging.getLogger("secure_rag.audit")
logger.setLevel(logging.INFO)
logger.propagate = False

LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

if not logger.handlers:
    handler = logging.FileHandler(
        LOG_PATH,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)


def audit_event(
    event_type: str,
    request_id: str,
    username: str,
    outcome: str,
    document_ids=None,
    **details,
):
    # Explicit allowlist of additional audit attributes.
    permitted_details = {
        "reason",
        "document_count",
        "content_filter_triggered",
    }

    safe_details = {
        key: value
        for key, value in details.items()
        if key in permitted_details
        and isinstance(value, (str, int, bool))
    }

    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "request_id": request_id,
        "username": username,
        "outcome": outcome,
        "document_ids": list(document_ids or []),
        **safe_details,
    }

    logger.info(json.dumps(event, ensure_ascii=False))
