from app.hubspot import format_hubspot_internal_note, parse_ticket_events
from app.schemas import (
    Citation,
    DecisionResult,
    Outcome,
    ProcessedTicket,
    TicketAnalysis,
    TicketInput,
)


def test_parse_ticket_events_uses_only_ticket_events() -> None:
    payload = [
        {"subscriptionType": "ticket.creation", "objectId": 101, "eventId": 201},
        {"subscriptionType": "contact.creation", "objectId": 102, "eventId": 202},
        {"subscriptionType": "ticket.propertyChange", "objectId": "103", "eventId": "203"},
        {
            "subscriptionType": "object.creation",
            "objectTypeId": "0-5",
            "objectId": "104",
            "eventId": "204",
        },
        {
            "subscriptionType": "object.creation",
            "objectTypeId": "0-1",
            "objectId": "105",
            "eventId": "205",
        },
    ]

    events = parse_ticket_events(payload)

    assert [(event.ticket_id, event.event_id) for event in events] == [
        (101, "201"),
        (103, "203"),
        (104, "204"),
    ]


def test_parse_ticket_events_ignores_malformed_events() -> None:
    assert parse_ticket_events([{"subscriptionType": "ticket.creation"}, "not-an-event"]) == []


def test_parse_ticket_events_supports_hubspot_sized_object_ids() -> None:
    events = parse_ticket_events(
        [{"subscriptionType": "ticket.creation", "objectId": "424953015487", "eventId": "204"}]
    )

    assert events[0].ticket_id == 424953015487


def test_format_hubspot_internal_note_is_concise_and_structured() -> None:
    result = ProcessedTicket(
        ticket=TicketInput(ticket_id=1, subject="Invoice", description="Where is my invoice?"),
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
        suggested_reply="You can download invoices from Settings > Billing.",
    )

    note = format_hubspot_internal_note(result)

    assert "<h3>AI triage</h3>" in note
    assert "Billing and Invoice Guide.pdf (p. 1)" in note
    assert "score" not in note
    assert "Suggested reply" in note
    assert "No customer message was sent." in note
