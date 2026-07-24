import base64

import httpx

from app.config import Settings
from app.schemas import TicketInput


class ZendeskClient:
    def __init__(self, settings: Settings):
        if not all((settings.zendesk_subdomain, settings.zendesk_email, settings.zendesk_api_token)):
            raise ValueError("Zendesk client requires subdomain, email, and API token")
        self.base_url = f"https://{settings.zendesk_subdomain}.zendesk.com/api/v2"
        token = base64.b64encode(f"{settings.zendesk_email}/token:{settings.zendesk_api_token}".encode()).decode()
        self.headers = {"Authorization": f"Basic {token}", "Content-Type": "application/json"}

    async def fetch_ticket(self, ticket_id: int, source_event_id: str | None) -> TicketInput:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(f"{self.base_url}/tickets/{ticket_id}.json", headers=self.headers)
            response.raise_for_status()
        ticket = response.json()["ticket"]
        return TicketInput(ticket_id=ticket["id"], subject=ticket["subject"] or "(no subject)", description=ticket["description"] or "(no description)", priority=ticket.get("priority"), source_event_id=source_event_id)

    async def add_private_note(self, ticket_id: int, note: str) -> None:
        payload = {"ticket": {"comment": {"body": note, "public": False}}}
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.put(f"{self.base_url}/tickets/{ticket_id}.json", headers=self.headers, json=payload)
            response.raise_for_status()
