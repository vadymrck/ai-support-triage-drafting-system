import asyncio
import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock

import httpx

from app import main as app_main
from app.config import Settings
from app.schemas import (
    Citation,
    DecisionResult,
    Outcome,
    ProcessedTicket,
    TicketAnalysis,
    TicketInput,
)


def _signature(secret: str, uri: str, body: bytes, timestamp: str) -> str:
    source = f"POST{uri}{body.decode('utf-8')}{timestamp}"
    digest = hmac.new(secret.encode(), source.encode(), hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def test_signed_ticket_webhook_queues_background_processing(monkeypatch) -> None:
    secret = "test-client-secret"
    webhook_url = "https://example.test/v1/webhooks/hubspot"
    settings = Settings(
        hubspot_private_app_access_token="test-access-token",
        hubspot_private_app_client_secret=secret,
        hubspot_webhook_base_url="https://example.test",
    )
    payload = [
        {
            "subscriptionType": "object.creation",
            "objectTypeId": "0-5",
            "objectId": "424953015487",
            "eventId": "event-123",
        }
    ]
    body = json.dumps(payload, separators=(",", ":")).encode()
    timestamp = str(int(datetime.now(UTC).timestamp() * 1_000))
    hubspot_client = Mock()
    background_processor = AsyncMock()

    monkeypatch.setattr(app_main, "get_settings", lambda: settings)
    monkeypatch.setattr(app_main, "HubSpotClient", lambda _: hubspot_client)
    monkeypatch.setattr(app_main, "process_hubspot_event", background_processor)

    async def send_webhook() -> httpx.Response:
        transport = httpx.ASGITransport(app=app_main.app)
        async with httpx.AsyncClient(
            transport=transport, base_url="https://example.test"
        ) as client:
            return await client.post(
                "/v1/webhooks/hubspot",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-HubSpot-Signature-V3": _signature(secret, webhook_url, body, timestamp),
                    "X-HubSpot-Request-Timestamp": timestamp,
                },
            )

    response = asyncio.run(send_webhook())

    assert response.status_code == 202
    assert response.json() == {"status": "accepted", "event_count": 1}
    background_processor.assert_awaited_once()
    ticket_id, event_id, queued_client, queued_settings = background_processor.await_args.args
    assert ticket_id == 424953015487
    assert event_id == "event-123"
    assert queued_client is hubspot_client
    assert queued_settings is settings


def test_background_processing_syncs_an_internal_note_when_enabled(monkeypatch) -> None:
    class EmptyDecisionSession:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def scalar(self, _):
            return None

    settings = Settings(hubspot_note_sync_enabled=True)
    session = EmptyDecisionSession()
    hubspot_client = Mock()
    ticket = TicketInput(
        ticket_id=424953015487,
        subject="Invoice location",
        description="Where can I find my invoice?",
        source_event_id="event-123",
    )
    result = ProcessedTicket(
        ticket=ticket,
        analysis=TicketAnalysis(
            issue_type="Billing",
            urgency="normal",
            sentiment="neutral",
            confidence=0.9,
            summary="Customer asks where an account owner can download an invoice.",
        ),
        citations=[
            Citation(
                document_title="Billing and Invoice Guide.pdf",
                page_number=1,
                excerpt="Invoices are available in Billing.",
                score=0.8,
            )
        ],
        decision=DecisionResult(
            outcome=Outcome.DRAFT_READY,
            reason="Grounded in the knowledge base.",
            recommended_action="Review and manually send the suggested reply.",
        ),
        internal_note="Full local audit record.",
        suggested_reply="Hello,\n\nYou can download invoices from Settings > Billing.\n\nBest,\nSupport Team",
    )
    hubspot_client.fetch_ticket = AsyncMock(return_value=ticket)
    hubspot_client.add_internal_note = AsyncMock()
    process_ticket_mock = Mock(return_value=result)

    monkeypatch.setattr(app_main, "SessionLocal", lambda: session)
    monkeypatch.setattr(app_main, "process_ticket", process_ticket_mock)

    asyncio.run(
        app_main.process_hubspot_event(ticket.ticket_id, "event-123", hubspot_client, settings)
    )

    process_ticket_mock.assert_called_once_with(session, ticket, settings)
    hubspot_client.add_internal_note.assert_awaited_once()
    synced_ticket_id, note = hubspot_client.add_internal_note.await_args.args
    assert synced_ticket_id == ticket.ticket_id
    assert "<h3>AI triage</h3>" in note
    assert "Suggested reply" in note
