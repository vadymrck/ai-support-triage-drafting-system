import re
from pathlib import Path

from openai import OpenAI
from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import KnowledgeChunk, TicketDecisionRecord
from app.policy import decide, detect_sensitive_topics, has_escalated_sentiment
from app.schemas import Citation, Outcome, ProcessedTicket, TicketAnalysis, TicketInput


def _terms(text: str) -> set[str]:
    return {term for term in re.findall(r"[a-zA-Z]{3,}", text.lower())}


class TicketAnalyzer:
    def __init__(self, settings: Settings):
        self.settings = settings

    def analyze(self, ticket: TicketInput) -> TicketAnalysis:
        if self.settings.execution_mode == "ai":
            if not self.settings.openai_api_key:
                raise ValueError("EXECUTION_MODE=ai requires OPENAI_API_KEY")
            client = OpenAI(api_key=self.settings.openai_api_key)
            completion = client.beta.chat.completions.parse(
                model=self.settings.openai_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Classify support tickets. Report observations only; never decide routing. "
                            "Set missing_information=true only when the ticket lacks enough information to classify the issue "
                            "or recommend an initial next step. Do not set it merely because an agent may later need details "
                            "to complete troubleshooting, such as identity-provider configuration."
                        ),
                    },
                    {"role": "user", "content": f"Subject: {ticket.subject}\n\nTicket: {ticket.description}"},
                ],
                response_format=TicketAnalysis,
            )
            parsed = completion.choices[0].message.parsed
            if parsed is None:
                raise ValueError("OpenAI returned no structured ticket analysis")
            return parsed
        return self._heuristic_analysis(ticket)

    @staticmethod
    def _heuristic_analysis(ticket: TicketInput) -> TicketAnalysis:
        text = f"{ticket.subject} {ticket.description}".lower()
        sensitive_topics: list[str] = []
        for topic, markers in {
            "security": ("breach", "security incident", "hacked"),
            "account_compromise": ("account compromised", "unauthorized access"),
            "privacy": ("personal data", "gdpr"),
            "account_deletion": ("delete my account", "delete our data"),
            "payment_dispute": ("chargeback", "dispute this charge"),
            "legal": ("lawyer", "legal notice"),
        }.items():
            if any(marker in text for marker in markers):
                sensitive_topics.append(topic)
        urgency = "critical" if any(word in text for word in ("outage", "entire team is blocked", "production down")) else "normal"
        issue_type = "access" if any(word in text for word in ("sign in", "login", "sso", "password")) else "general_request"
        return TicketAnalysis(
            issue_type=issue_type,
            product_area="identity" if issue_type == "access" else None,
            urgency=urgency,
            sentiment="frustrated" if any(word in text for word in ("frustrated", "unacceptable", "angry")) else "neutral",
            sensitive_topics=sensitive_topics,
            confidence=0.80,
            summary=f"{issue_type.replace('_', ' ').title()} ticket received.",
        )


class KnowledgeService:
    def __init__(self, settings: Settings):
        self.settings = settings

    def ingest_pdf(self, session: Session, path: Path) -> int:
        reader = PdfReader(str(path))
        count = 0
        for page_number, page in enumerate(reader.pages, start=1):
            content = (page.extract_text() or "").strip()
            if not content:
                continue
            for chunk in _chunk_text(content):
                embedding = self._embed(chunk) if self.settings.execution_mode == "ai" else None
                session.add(KnowledgeChunk(document_title=path.name, page_number=page_number, content=chunk, embedding=embedding))
                count += 1
        session.commit()
        return count

    def retrieve(self, session: Session, query: str, limit: int = 3) -> list[Citation]:
        query_embedding = self._embed(query) if self.settings.execution_mode == "ai" else None
        if query_embedding:
            distance = KnowledgeChunk.embedding.cosine_distance(query_embedding)
            rows = session.execute(select(KnowledgeChunk, distance.label("distance")).order_by(distance).limit(limit)).all()
            return [Citation(document_title=row.document_title, page_number=row.page_number, excerpt=row.content, score=round(1 - float(distance), 3)) for row, distance in rows]
        query_terms = _terms(query)
        rows = session.scalars(select(KnowledgeChunk)).all()
        ranked = sorted(((len(query_terms & _terms(row.content)) / max(len(query_terms), 1), row) for row in rows), reverse=True, key=lambda item: item[0])
        return [Citation(document_title=row.document_title, page_number=row.page_number, excerpt=row.content, score=round(score, 3)) for score, row in ranked[:limit] if score > 0]

    def _embed(self, text: str) -> list[float]:
        if self.settings.execution_mode != "ai" or not self.settings.openai_api_key:
            raise ValueError("Embedding generation requires EXECUTION_MODE=ai and OPENAI_API_KEY")
        client = OpenAI(api_key=self.settings.openai_api_key)
        return client.embeddings.create(model=self.settings.openai_embedding_model, input=text).data[0].embedding


def _chunk_text(text: str, max_characters: int = 1_200) -> list[str]:
    return [text[index:index + max_characters].strip() for index in range(0, len(text), max_characters) if text[index:index + max_characters].strip()]


def process_ticket(session: Session, ticket: TicketInput, settings: Settings | None = None) -> ProcessedTicket:
    settings = settings or get_settings()
    analysis = TicketAnalyzer(settings).analyze(ticket)
    ticket_text = f"{ticket.subject}\n{ticket.description}"
    deterministic_sensitive_topics = detect_sensitive_topics(ticket_text)
    analysis.sensitive_topics = sorted(set(analysis.sensitive_topics) | set(deterministic_sensitive_topics))
    if has_escalated_sentiment(ticket_text):
        analysis.sentiment = "escalated"
    citations = KnowledgeService(settings).retrieve(session, f"{ticket.subject}\n{ticket.description}")
    best_score = citations[0].score if citations else 0.0
    decision = decide(analysis, len(citations), best_score)
    suggested_reply = DraftGenerator(settings).generate(ticket, citations) if decision.outcome == Outcome.DRAFT_READY else None
    internal_note = _internal_note(analysis, citations, decision, suggested_reply)
    record = TicketDecisionRecord(
        ticket_id=ticket.ticket_id,
        source_event_id=ticket.source_event_id,
        outcome=decision.outcome.value,
        analysis=analysis.model_dump(),
        citations=[citation.model_dump() for citation in citations],
        internal_note=internal_note,
        suggested_reply=suggested_reply,
    )
    session.add(record)
    session.commit()
    return ProcessedTicket(ticket=ticket, analysis=analysis, citations=citations, decision=decision, internal_note=internal_note, suggested_reply=suggested_reply)


class DraftGenerator:
    """Creates a customer-facing suggestion only after deterministic policy permits it."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def generate(self, ticket: TicketInput, citations: list[Citation]) -> str:
        if self.settings.execution_mode == "ai":
            if not self.settings.openai_api_key:
                raise ValueError("EXECUTION_MODE=ai requires OPENAI_API_KEY")
            evidence = "\n\n".join(
                f"SOURCE: {citation.document_title}, page {citation.page_number}\n{citation.excerpt}" for citation in citations
            )
            client = OpenAI(api_key=self.settings.openai_api_key)
            completion = client.chat.completions.create(
                model=self.settings.openai_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Draft a concise, professional customer-support reply. Use only the supplied evidence. "
                            "Do not invent product behavior, make promises, mention internal policy, or claim an action was completed. "
                            "Do not add a prerequisite, navigation instruction, verification step, or access instruction unless it is explicitly stated in the evidence. "
                            "Include a directly relevant safety or verification boundary when the evidence requires one; do not replace it with an invented equivalent. "
                            "If the evidence does not support a detail, omit it. Return only the proposed customer reply."
                        ),
                    },
                    {"role": "user", "content": f"Ticket subject: {ticket.subject}\nTicket: {ticket.description}\n\nEvidence:\n{evidence}"},
                ],
            )
            content = completion.choices[0].message.content
            if not content:
                raise ValueError("OpenAI returned an empty draft")
            return content.strip()
        return self._heuristic_draft(ticket, citations)

    @staticmethod
    def _heuristic_draft(ticket: TicketInput, citations: list[Citation]) -> str:
        sources = "; ".join(f"{citation.document_title}, p. {citation.page_number}" for citation in citations)
        return f"Thanks for contacting support about {ticket.subject.lower()}. Based on our support guidance, please follow the documented steps and reply with the requested details if the issue continues. Sources for agent review: {sources}."


def _internal_note(analysis: TicketAnalysis, citations: list[Citation], decision, suggested_reply: str | None) -> str:
    citation_lines = "\n".join(f"- {c.document_title}, p. {c.page_number} (score {c.score})" for c in citations) or "- No adequate knowledge-base evidence retrieved"
    parts = [
        "AI triage — internal use only",
        f"Outcome: {decision.outcome.value}",
        f"Reason: {decision.reason}",
        f"Summary: {analysis.summary}",
        f"Recommended action: {decision.recommended_action}",
        "Retrieved evidence:",
        citation_lines,
    ]
    if suggested_reply:
        parts.extend(["Suggested reply — human review required before sending:", suggested_reply])
    return "\n\n".join(parts)
