import base64
import hashlib
import hmac
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException

from app.security import verify_hubspot_signature


def _hubspot_signature(body: bytes, timestamp: str, secret: str) -> str:
    source = f"POSThttps://example.ngrok.app/v1/webhooks/hubspot{body.decode()}{timestamp}"
    return base64.b64encode(
        hmac.new(secret.encode(), source.encode(), hashlib.sha256).digest()
    ).decode()


def test_accepts_valid_hubspot_signature() -> None:
    body = b'{"ticket_id":123}'
    timestamp = str(int(datetime.now(UTC).timestamp() * 1_000))
    secret = "test-secret"
    signature = _hubspot_signature(body, timestamp, secret)
    verify_hubspot_signature(
        "POST",
        "https://example.ngrok.app/v1/webhooks/hubspot",
        body,
        signature,
        timestamp,
        secret,
        300,
    )


def test_rejects_invalid_signature() -> None:
    timestamp = str(int(datetime.now(UTC).timestamp() * 1_000))
    with pytest.raises(HTTPException, match="Invalid HubSpot webhook signature"):
        verify_hubspot_signature(
            "POST",
            "https://example.ngrok.app/v1/webhooks/hubspot",
            b"{}",
            "bad",
            timestamp,
            "test-secret",
            300,
        )


def test_rejects_expired_signature_even_when_digest_is_valid() -> None:
    body = b'{"ticket_id":123}'
    timestamp = str(int((datetime.now(UTC) - timedelta(seconds=301)).timestamp() * 1_000))
    secret = "test-secret"
    signature = _hubspot_signature(body, timestamp, secret)

    with pytest.raises(HTTPException, match="Expired webhook signature"):
        verify_hubspot_signature(
            "POST",
            "https://example.ngrok.app/v1/webhooks/hubspot",
            body,
            signature,
            timestamp,
            secret,
            300,
        )
