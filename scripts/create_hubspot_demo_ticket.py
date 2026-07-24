"""Create a synthetic HubSpot ticket for a local webhook verification."""

import argparse
import asyncio

import httpx

from app.config import get_settings

HUBSPOT_API_BASE_URL = "https://api.hubapi.com"


async def create_ticket(subject: str, description: str, priority: str | None) -> str:
    settings = get_settings()
    token = settings.hubspot_private_app_access_token
    if not token:
        raise SystemExit("HUBSPOT_PRIVATE_APP_ACCESS_TOKEN is required.")

    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=15) as client:
        pipelines_response = await client.get(
            f"{HUBSPOT_API_BASE_URL}/crm/v3/pipelines/tickets", headers=headers
        )
        pipelines_response.raise_for_status()
        pipelines = pipelines_response.json().get("results", [])
        if not pipelines or not pipelines[0].get("stages"):
            raise SystemExit("No ticket pipeline and stage are available in this HubSpot account.")

        pipeline = pipelines[0]
        properties = {
            "hs_pipeline": pipeline["id"],
            "hs_pipeline_stage": pipeline["stages"][0]["id"],
            "subject": subject,
            "content": description,
        }
        if priority:
            properties["hs_ticket_priority"] = priority
        ticket_response = await client.post(
            f"{HUBSPOT_API_BASE_URL}/crm/v3/objects/tickets",
            headers=headers,
            json={"properties": properties},
        )
        ticket_response.raise_for_status()
    return str(ticket_response.json()["id"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subject", required=True)
    parser.add_argument("--description", required=True)
    parser.add_argument("--priority", choices=["LOW", "MEDIUM", "HIGH"], default="MEDIUM")
    args = parser.parse_args()

    ticket_id = asyncio.run(create_ticket(args.subject, args.description, args.priority))
    print(f"Created HubSpot demo ticket: {ticket_id}")


if __name__ == "__main__":
    main()
