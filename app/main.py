import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import SessionLocal, TicketDecisionRecord, get_session, initialize_database
from app.hubspot import HubSpotClient, format_hubspot_internal_note, parse_ticket_events
from app.schemas import ProcessedTicket, TicketInput
from app.security import verify_hubspot_signature
from app.services import process_ticket

logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    initialize_database()
    yield


app = FastAPI(
    title="AI Support Triage & Drafting System",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post(
    "/v1/tickets/process", response_model=ProcessedTicket, status_code=status.HTTP_201_CREATED
)
def process_local_ticket(
    ticket: TicketInput, session: Session = Depends(get_session)
) -> ProcessedTicket:
    return process_ticket(session, ticket)


@app.post("/v1/webhooks/hubspot", status_code=status.HTTP_202_ACCEPTED)
async def receive_hubspot_webhook(
    request: Request, background_tasks: BackgroundTasks
) -> dict[str, str | int]:
    settings = get_settings()
    body = await request.body()
    webhook_uri = (settings.hubspot_webhook_base_url or str(request.base_url)).rstrip(
        "/"
    ) + request.url.path
    if request.url.query:
        webhook_uri += f"?{request.url.query}"
    verify_hubspot_signature(
        method=request.method,
        uri=webhook_uri,
        body=body,
        signature=request.headers.get("x-hubspot-signature-v3"),
        timestamp=request.headers.get("x-hubspot-request-timestamp"),
        secret=settings.hubspot_private_app_client_secret,
        max_age_seconds=settings.webhook_max_age_seconds,
    )
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Webhook payload is not valid JSON",
        ) from error
    events = parse_ticket_events(payload)
    subscription_types = (
        [str(event.get("subscriptionType")) for event in payload if isinstance(event, dict)]
        if isinstance(payload, list)
        else []
    )
    logger.warning(
        "HubSpot webhook received: subscriptions=%s parsed_events=%s",
        subscription_types,
        len(events),
    )
    if not events:
        return {"status": "ignored"}

    client = HubSpotClient(settings)
    for event in events:
        logger.warning(
            "HubSpot event queued: ticket_id=%s event_id=%s", event.ticket_id, event.event_id
        )
        background_tasks.add_task(
            process_hubspot_event, event.ticket_id, event.event_id, client, settings
        )
    return {"status": "accepted", "event_count": len(events)}


async def process_hubspot_event(
    ticket_id: int, event_id: str, client: HubSpotClient, settings: Settings
) -> None:
    try:
        logger.warning(
            "HubSpot event processing started: ticket_id=%s event_id=%s", ticket_id, event_id
        )
        with SessionLocal() as session:
            if session.scalar(
                select(TicketDecisionRecord).where(TicketDecisionRecord.source_event_id == event_id)
            ):
                return
            ticket = await client.fetch_ticket(ticket_id, event_id)
            result = process_ticket(session, ticket, settings)
            if settings.hubspot_note_sync_enabled:
                await client.add_internal_note(
                    ticket.ticket_id, format_hubspot_internal_note(result)
                )
        logger.warning("HubSpot event processing completed: ticket_id=%s", ticket_id)
    except Exception:
        logger.exception(
            "HubSpot event processing failed: ticket_id=%s event_id=%s", ticket_id, event_id
        )
