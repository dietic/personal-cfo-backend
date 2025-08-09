import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

_logger = logging.getLogger("audit")


def _email_hash(email: Optional[str]) -> Optional[str]:
    if not email:
        return None
    h = hashlib.sha256(email.lower().encode()).hexdigest()
    return h[:12]


def audit(event: str, *, email: Optional[str] = None, user_id: Optional[str] = None, **fields: Any) -> None:
    """Emit a minimally structured audit log as a single JSON line.

    Never include secrets like OTP or passwords. Email is hashed to limit PII exposure.
    """
    payload: Dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
    }
    if email:
        payload["email_hash"] = _email_hash(email)
    if user_id:
        payload["user_id"] = user_id
    if fields:
        payload.update(fields)
    try:
        _logger.info(json.dumps(payload, ensure_ascii=False))
    except Exception:
        # Fallback to plain message if JSON logging fails
        _logger.info(f"AUDIT {event} email_hash={payload.get('email_hash')} user_id={user_id} fields={fields}")
