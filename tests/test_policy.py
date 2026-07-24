from app.policy import decide, detect_sensitive_topics, has_escalated_sentiment
from app.judging import DraftQualityAssessment, passes_draft_quality
from app.schemas import Outcome, TicketAnalysis


def analysis(**overrides) -> TicketAnalysis:
    defaults = {
        "issue_type": "access",
        "urgency": "normal",
        "sentiment": "neutral",
        "confidence": 0.9,
        "summary": "Access request.",
    }
    return TicketAnalysis(**(defaults | overrides))


def test_sensitive_ticket_overrides_good_retrieval() -> None:
    result = decide(analysis(sensitive_topics=["security"]), citation_count=3, best_retrieval_score=0.9)
    assert result.outcome == Outcome.REVIEW_REQUIRED


def test_deterministic_privacy_marker_detects_deletion_request() -> None:
    assert set(detect_sensitive_topics("Please delete our data under GDPR.")) == {"privacy", "account_deletion"}


def test_escalated_sentiment_requires_human_review() -> None:
    assert has_escalated_sentiment("I am tired of waiting for a response.")
    assert decide(analysis(sentiment="escalated"), citation_count=3, best_retrieval_score=0.9).outcome == Outcome.REVIEW_REQUIRED


def test_low_confidence_requires_review() -> None:
    result = decide(analysis(confidence=0.69), citation_count=3, best_retrieval_score=0.9)
    assert result.outcome == Outcome.REVIEW_REQUIRED


def test_missing_evidence_requires_knowledge_update() -> None:
    result = decide(analysis(), citation_count=0, best_retrieval_score=0.0)
    assert result.outcome == Outcome.NEEDS_KNOWLEDGE_UPDATE


def test_grounded_safe_ticket_is_draft_ready() -> None:
    result = decide(analysis(), citation_count=2, best_retrieval_score=0.40)
    assert result.outcome == Outcome.DRAFT_READY


def test_draft_quality_gate_requires_grounding_and_safety() -> None:
    assert passes_draft_quality(DraftQualityAssessment(grounding=2, helpfulness=2, tone=1, safety=2, improvement_note="Minor tone edit."))
    assert not passes_draft_quality(DraftQualityAssessment(grounding=1, helpfulness=2, tone=2, safety=2, improvement_note="Remove unsupported claim."))
