import json

from fastapi import Depends, FastAPI, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import TicketDecisionRecord, get_session, initialize_database
from app.schemas import ProcessedTicket, TicketInput
from app.security import verify_zendesk_signature
from app.services import process_ticket
from app.zendesk import ZendeskClient

app = FastAPI(title="AI Support Triage & Drafting System", version="0.1.0")


@app.on_event("startup")
def startup() -> None:
    initialize_database()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/tickets/process", response_model=ProcessedTicket, status_code=status.HTTP_201_CREATED)
def process_local_ticket(ticket: TicketInput, session: Session = Depends(get_session)) -> ProcessedTicket:
    return process_ticket(session, ticket)


@app.post("/v1/webhooks/zendesk", status_code=status.HTTP_202_ACCEPTED)
async def receive_zendesk_webhook(request: Request, session: Session = Depends(get_session)) -> dict[str, str]:
    settings = get_settings()
    body = await request.body()
    verify_zendesk_signature(
        body=body,
        signature=request.headers.get("x-zendesk-webhook-signature"),
        timestamp=request.headers.get("x-zendesk-webhook-signature-timestamp"),
        secret=settings.zendesk_webhook_signing_secret,
        max_age_seconds=settings.webhook_max_age_seconds,
    )
    try:
        payload = json.loads(body)
        ticket_id = int(payload.get("ticket_id") or payload.get("ticket", {}).get("id") or payload.get("data", {}).get("ticket", {}).get("id"))
    except (AttributeError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Webhook payload does not contain a ticket ID") from error
    event_id = request.headers.get("x-zendesk-webhook-invocation-id")
    if event_id and session.scalar(select(TicketDecisionRecord).where(TicketDecisionRecord.source_event_id == event_id)):
        return {"status": "duplicate_ignored"}
    client = ZendeskClient(settings)
    ticket = await client.fetch_ticket(ticket_id, event_id)
    result = process_ticket(session, ticket, settings)
    if settings.zendesk_note_sync_enabled:
        await client.add_private_note(ticket.ticket_id, result.internal_note)
    return {"status": "processed", "outcome": result.decision.outcome.value}
