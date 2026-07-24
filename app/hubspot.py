import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from html import escape
from typing import Any

import httpx

from app.config import Settings
from app.schemas import ProcessedTicket, TicketInput

HUBSPOT_API_BASE_URL = "https://api.hubapi.com"
NOTE_TO_TICKET_ASSOCIATION_TYPE_ID = 228
HUBSPOT_TICKET_OBJECT_TYPE_ID = "0-5"


@dataclass(frozen=True)
class HubSpotTicketEvent:
    ticket_id: int
    event_id: str


def format_hubspot_internal_note(result: ProcessedTicket) -> str:
    """Render a compact, support-agent-friendly note for HubSpot's rich-text timeline."""
    outcome = result.decision.outcome.value.replace("_", " ").title()
    evidence = "".join(
        f"<li>{escape(citation.document_title)} (p. {citation.page_number})</li>"
        for citation in result.citations[:2]
    )
    sections = [
        "<h3>AI triage</h3>",
        f"<p><strong>Outcome:</strong> {outcome}</p>",
        f"<p><strong>Summary:</strong><br>{escape(result.analysis.summary)}</p>",
        f"<p><strong>Next step:</strong><br>{escape(result.decision.recommended_action)}</p>",
    ]
    if result.decision.outcome.value == "review_required":
        sections.append(f"<p><strong>Why review:</strong><br>{escape(result.decision.reason)}</p>")
    if evidence:
        sections.append(f"<p><strong>Knowledge used:</strong></p><ul>{evidence}</ul>")
    if result.suggested_reply:
        draft = escape(result.suggested_reply).replace("\n", "<br>")
        sections.append(
            "<hr><p><strong>Suggested reply — review and edit before sending:</strong></p>"
            f"<blockquote>{draft}</blockquote>"
        )
    else:
        sections.append(
            "<p><strong>Customer reply:</strong> Not drafted; human review is required.</p>"
        )
    sections.append("<p><em>Internal AI triage note. No customer message was sent.</em></p>")
    return "".join(sections)


def parse_ticket_events(payload: Any) -> list[HubSpotTicketEvent]:
    """Return ticket events from HubSpot's batched webhook payload."""
    events = payload if isinstance(payload, list) else [payload]
    parsed_events: list[HubSpotTicketEvent] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        subscription_type = str(event.get("subscriptionType", ""))
        is_legacy_ticket_event = subscription_type.startswith("ticket.")
        is_ticket_creation = (
            subscription_type == "object.creation"
            and str(event.get("objectTypeId")) == HUBSPOT_TICKET_OBJECT_TYPE_ID
        )
        if not (is_legacy_ticket_event or is_ticket_creation):
            continue
        try:
            parsed_events.append(
                HubSpotTicketEvent(ticket_id=int(event["objectId"]), event_id=str(event["eventId"]))
            )
        except (KeyError, TypeError, ValueError):
            continue
    return parsed_events


class HubSpotClient:
    def __init__(self, settings: Settings):
        if not settings.hubspot_private_app_access_token:
            raise ValueError("HubSpot client requires HUBSPOT_PRIVATE_APP_ACCESS_TOKEN")
        self.headers = {
            "Authorization": f"Bearer {settings.hubspot_private_app_access_token}",
            "Content-Type": "application/json",
        }

    async def fetch_ticket(self, ticket_id: int, source_event_id: str) -> TicketInput:
        params = {"properties": "subject,content,hs_ticket_priority"}
        async with httpx.AsyncClient(timeout=15) as client:
            for attempt in range(3):
                response = await client.get(
                    f"{HUBSPOT_API_BASE_URL}/crm/v3/objects/tickets/{ticket_id}",
                    headers=self.headers,
                    params=params,
                )
                if response.status_code != 404 or attempt == 2:
                    response.raise_for_status()
                    break
                await asyncio.sleep(2**attempt)
        properties = response.json().get("properties", {})
        return TicketInput(
            ticket_id=ticket_id,
            subject=properties.get("subject") or "(no subject)",
            description=properties.get("content") or "(no description)",
            priority=properties.get("hs_ticket_priority"),
            source_event_id=source_event_id,
        )

    async def add_internal_note(self, ticket_id: int, note: str) -> None:
        payload = {
            "properties": {
                "hs_timestamp": datetime.now(UTC).isoformat(),
                "hs_note_body": note,
            },
            "associations": [
                {
                    "to": {"id": str(ticket_id)},
                    "types": [
                        {
                            "associationCategory": "HUBSPOT_DEFINED",
                            "associationTypeId": NOTE_TO_TICKET_ASSOCIATION_TYPE_ID,
                        }
                    ],
                }
            ],
        }
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                f"{HUBSPOT_API_BASE_URL}/crm/v3/objects/notes",
                headers=self.headers,
                json=payload,
            )
            response.raise_for_status()
