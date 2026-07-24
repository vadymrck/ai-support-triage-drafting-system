import base64
import hashlib
import hmac
from datetime import UTC, datetime
from urllib.parse import unquote

from fastapi import HTTPException, status


def verify_hubspot_signature(
    method: str,
    uri: str,
    body: bytes,
    signature: str | None,
    timestamp: str | None,
    secret: str | None,
    max_age_seconds: int,
) -> None:
    """Validate HubSpot's v3 base64(HMAC-SHA256) webhook signature."""
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook verification is not configured",
        )
    if not signature or not timestamp:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing HubSpot signature headers"
        )
    try:
        signed_at = datetime.fromtimestamp(int(timestamp) / 1_000, UTC)
    except (TypeError, ValueError, OSError) as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature timestamp"
        ) from error
    if abs((datetime.now(UTC) - signed_at).total_seconds()) > max_age_seconds:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Expired webhook signature"
        )
    source = f"{method.upper()}{unquote(uri)}{body.decode('utf-8')}{timestamp}"
    expected = hmac.new(secret.encode(), source.encode(), hashlib.sha256).digest()
    expected_signature = base64.b64encode(expected).decode()
    if not hmac.compare_digest(expected_signature, signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid HubSpot webhook signature"
        )
