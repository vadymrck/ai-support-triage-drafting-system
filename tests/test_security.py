import base64
import hashlib
import hmac
from datetime import UTC, datetime

import pytest
from fastapi import HTTPException

from app.security import verify_zendesk_signature


def test_accepts_valid_zendesk_signature() -> None:
    body = b'{"ticket_id":123}'
    timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    secret = "test-secret"
    signature = base64.b64encode(hmac.new(secret.encode(), timestamp.encode() + body, hashlib.sha256).digest()).decode()
    verify_zendesk_signature(body, signature, timestamp, secret, 300)


def test_rejects_invalid_signature() -> None:
    with pytest.raises(HTTPException, match="Invalid Zendesk webhook signature"):
        verify_zendesk_signature(b"{}", "bad", datetime.now(UTC).isoformat(), "test-secret", 300)
