from app.schemas import DecisionResult, Outcome, TicketAnalysis

SENSITIVE_TOPICS = {
    "security",
    "account_compromise",
    "privacy",
    "account_deletion",
    "payment_dispute",
    "legal",
    "abuse",
}

SENSITIVE_MARKERS = {
    "security": ("breach", "security incident", "hacked"),
    "account_compromise": ("account compromised", "unauthorized access"),
    "privacy": ("personal data", "gdpr", "data privacy"),
    "account_deletion": ("delete my account", "delete our data", "delete my data", "erase our data"),
    "payment_dispute": ("chargeback", "dispute this charge", "dispute the charge"),
    "legal": ("lawyer", "legal notice", "legal request"),
    "abuse": ("harassment", "threatening"),
}

ESCALATED_SENTIMENT_MARKERS = (
    "tired of waiting",
    "tired for waiting",
    "waiting for a response",
    "waiting for response",
    "this is unacceptable",
    "speak to a manager",
)

# Demo calibration: both execution profiles currently share this floor, even
# though their retrieval scores come from different methods. Recalibrate it if
# the knowledge base, chunking strategy, or embedding model changes.
MIN_RETRIEVAL_SCORE = 0.40


def detect_sensitive_topics(text: str) -> list[str]:
    """Apply deterministic high-precision safety markers before draft generation."""
    normalized = text.lower()
    return [topic for topic, markers in SENSITIVE_MARKERS.items() if any(marker in normalized for marker in markers)]


def has_escalated_sentiment(text: str) -> bool:
    """Identify high-friction language that needs an agent's de-escalation judgment."""
    normalized = text.lower()
    return any(marker in normalized for marker in ESCALATED_SENTIMENT_MARKERS)


def decide(analysis: TicketAnalysis, citation_count: int, best_retrieval_score: float) -> DecisionResult:
    """Return the final business outcome without delegating routing to an LLM."""
    sensitive = sorted(set(analysis.sensitive_topics) & SENSITIVE_TOPICS)
    if sensitive:
        return DecisionResult(
            outcome=Outcome.REVIEW_REQUIRED,
            reason=f"Sensitive topic detected: {', '.join(sensitive)}.",
            recommended_action="Escalate to the appropriate support owner with the triage brief.",
        )
    if analysis.sentiment == "escalated":
        return DecisionResult(
            outcome=Outcome.REVIEW_REQUIRED,
            reason="Customer escalation language requires human de-escalation review.",
            recommended_action="Assign to a support agent for a tailored response and follow-up.",
        )
    if analysis.urgency == "critical":
        return DecisionResult(
            outcome=Outcome.REVIEW_REQUIRED,
            reason="Critical urgency requires human ownership.",
            recommended_action="Assign to on-call support or incident owner.",
        )
    if analysis.confidence < 0.70 or analysis.missing_information:
        return DecisionResult(
            outcome=Outcome.REVIEW_REQUIRED,
            reason="Ticket interpretation is incomplete or below the confidence threshold.",
            recommended_action="Review the ticket and request clarification where needed.",
        )
    if citation_count == 0 or best_retrieval_score < MIN_RETRIEVAL_SCORE:
        return DecisionResult(
            outcome=Outcome.NEEDS_KNOWLEDGE_UPDATE,
            reason="No sufficiently relevant knowledge-base evidence was retrieved.",
            recommended_action="Investigate the request and create or update the relevant knowledge article.",
        )
    return DecisionResult(
        outcome=Outcome.DRAFT_READY,
        reason="Ticket is non-sensitive, understood, and grounded in retrieved guidance.",
        recommended_action="Review, edit if needed, and manually send the suggested reply.",
    )
