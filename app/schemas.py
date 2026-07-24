from enum import StrEnum

from pydantic import BaseModel, Field


class Outcome(StrEnum):
    DRAFT_READY = "draft_ready"
    REVIEW_REQUIRED = "review_required"
    NEEDS_KNOWLEDGE_UPDATE = "needs_knowledge_update"


class TicketInput(BaseModel):
    ticket_id: int
    subject: str = Field(min_length=1, max_length=500)
    description: str = Field(min_length=1, max_length=20_000)
    requester_name: str | None = None
    priority: str | None = None
    source_event_id: str | None = None


class TicketAnalysis(BaseModel):
    issue_type: str
    product_area: str | None = None
    urgency: str
    sentiment: str
    sensitive_topics: list[str] = Field(default_factory=list)
    missing_information: bool = False
    confidence: float = Field(ge=0, le=1)
    summary: str


class Citation(BaseModel):
    document_title: str
    page_number: int
    excerpt: str
    score: float


class DecisionResult(BaseModel):
    outcome: Outcome
    reason: str
    recommended_action: str


class ProcessedTicket(BaseModel):
    ticket: TicketInput
    analysis: TicketAnalysis
    citations: list[Citation]
    decision: DecisionResult
    internal_note: str
    suggested_reply: str | None = None
