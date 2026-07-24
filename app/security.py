import base64
import hashlib
import hmac
from datetime import UTC, datetime

from fastapi import HTTPException, status


def verify_zendesk_signature(
    body: bytes, signature: str | None, timestamp: str | None, secret: str | None, max_age_seconds: int
) -> None:
    """Validate Zendesk's base64(HMAC-SHA256(timestamp + raw_body)) signature."""
    if not secret:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Webhook verification is not configured")
    if not signature or not timestamp:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Zendesk signature headers")
    try:
        signed_at = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature timestamp") from error
    if abs((datetime.now(UTC) - signed_at).total_seconds()) > max_age_seconds:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Expired webhook signature")
    digest = hmac.new(secret.encode(), timestamp.encode() + body, hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Zendesk webhook signature")
