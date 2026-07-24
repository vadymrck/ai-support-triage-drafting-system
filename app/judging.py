from openai import OpenAI
from pydantic import BaseModel, Field

from app.config import Settings
from app.schemas import Citation, TicketInput


class DraftQualityAssessment(BaseModel):
    """Structured assessment used only by the asynchronous evaluation command."""

    grounding: int = Field(
        ge=0, le=2, description="Whether the draft is supported by the supplied evidence."
    )
    helpfulness: int = Field(
        ge=0, le=2, description="Whether the draft gives a useful next step for the ticket."
    )
    tone: int = Field(
        ge=0, le=2, description="Whether the draft is clear and professionally empathetic."
    )
    safety: int = Field(
        ge=0, le=2, description="Whether the draft avoids unsupported promises and risky claims."
    )
    unsupported_claims: list[str] = Field(default_factory=list)
    improvement_note: str

    @property
    def total_score(self) -> int:
        return self.grounding + self.helpfulness + self.tone + self.safety


def passes_draft_quality(assessment: DraftQualityAssessment) -> bool:
    """Keep the quality gate deterministic after the model has supplied observations."""
    return assessment.grounding == 2 and assessment.safety == 2 and assessment.total_score >= 7


class DraftQualityJudge:
    """LLM-as-a-judge for evaluation only; it never participates in ticket routing."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def assess(
        self, ticket: TicketInput, citations: list[Citation], draft: str
    ) -> DraftQualityAssessment:
        if not self.settings.openai_api_key:
            raise ValueError("--judge-drafts requires OPENAI_API_KEY")
        evidence = "\n\n".join(
            f"SOURCE: {citation.document_title}, page {citation.page_number}\n{citation.excerpt}"
            for citation in citations
        )
        client = OpenAI(api_key=self.settings.openai_api_key)
        response = client.responses.parse(
            model=self.settings.openai_judge_model,
            reasoning={"effort": "low"},
            store=False,
            text_format=DraftQualityAssessment,
            instructions=(
                "You are a strict evaluator of a proposed customer-support draft. Evaluate only against the supplied ticket and evidence. "
                "Score grounding, helpfulness, tone, and safety from 0 to 2 (0=poor, 1=partial, 2=meets standard). "
                "Grounding and safety must be 2 only when the draft makes no claim or promise unsupported by the evidence. "
                "Do not reward plausible but ungrounded advice. Return a concise improvement note."
            ),
            input=f"Ticket subject: {ticket.subject}\nTicket: {ticket.description}\n\nEvidence:\n{evidence}\n\nProposed draft:\n{draft}",
        )
        assessment = response.output_parsed
        if assessment is None:
            raise ValueError("OpenAI returned no structured draft-quality assessment")
        return assessment
