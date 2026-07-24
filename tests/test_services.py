from app.config import Settings
from app.schemas import Outcome, TicketInput
from app.services import KnowledgeService, _chunk_text, process_ticket


class RecordingSession:
    def __init__(self) -> None:
        self.records = []
        self.committed = False

    def add(self, record) -> None:
        self.records.append(record)

    def commit(self) -> None:
        self.committed = True


def deterministic_settings() -> Settings:
    return Settings(execution_mode="deterministic")


def no_retrieval(monkeypatch) -> None:
    monkeypatch.setattr(KnowledgeService, "retrieve", lambda self, session, query: [])


def test_process_ticket_applies_deterministic_privacy_override(monkeypatch) -> None:
    no_retrieval(monkeypatch)
    session = RecordingSession()

    result = process_ticket(
        session,
        TicketInput(
            ticket_id=1,
            subject="Please delete our data",
            description="We need this handled under GDPR.",
        ),
        deterministic_settings(),
    )

    assert result.decision.outcome == Outcome.REVIEW_REQUIRED
    assert {"privacy", "account_deletion"}.issubset(result.analysis.sensitive_topics)
    assert session.committed


def test_process_ticket_applies_deterministic_escalation_override(monkeypatch) -> None:
    no_retrieval(monkeypatch)
    session = RecordingSession()

    result = process_ticket(
        session,
        TicketInput(
            ticket_id=2,
            subject="Need an update",
            description="I am tired of waiting for a response from support.",
        ),
        deterministic_settings(),
    )

    assert result.analysis.sentiment == "escalated"
    assert result.decision.outcome == Outcome.REVIEW_REQUIRED


def test_chunk_text_discards_blank_chunks_and_preserves_boundaries() -> None:
    assert _chunk_text("abcdef", max_characters=2) == ["ab", "cd", "ef"]
    assert _chunk_text("   ", max_characters=2) == []
