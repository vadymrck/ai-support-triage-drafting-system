import argparse
import json
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import SessionLocal, initialize_database
from app.judging import DraftQualityJudge, passes_draft_quality
from app.schemas import TicketInput
from app.services import process_ticket

EvaluationCase = dict[str, Any]
EvaluationRow = dict[str, Any]


def load_cases(
    dataset: Path, case_ids: list[str] | None, execution_mode: str
) -> list[EvaluationCase]:
    """Load, validate, select, and profile-filter synthetic evaluation fixtures."""
    all_cases: list[EvaluationCase] = json.loads(dataset.read_text())
    if case_ids:
        requested_ids = set(case_ids)
        found_ids = {case["id"] for case in all_cases}
        missing_ids = requested_ids - found_ids
        if missing_ids:
            raise SystemExit(f"Unknown evaluation case ID(s): {', '.join(sorted(missing_ids))}")
        all_cases = [case for case in all_cases if case["id"] in requested_ids]

    cases = [
        case for case in all_cases if execution_mode in case.get("modes", ["deterministic", "ai"])
    ]
    if not cases:
        requested = ", ".join(case_ids) if case_ids else "the dataset"
        raise SystemExit(
            f"No evaluation cases from {requested} apply to EXECUTION_MODE={execution_mode}."
        )
    return cases


def evaluate_case(
    session: Session,
    case: EvaluationCase,
    settings: Settings,
    judge: DraftQualityJudge | None,
) -> EvaluationRow:
    """Run one fixture through the workflow and return its machine-readable result."""
    ticket = TicketInput(**case["ticket"])
    result = process_ticket(session, ticket, settings)
    expected_document = case["expected_document"]
    outcome_match = result.decision.outcome.value == case["expected_outcome"]
    evidence_match = expected_document is None or any(
        citation.document_title == expected_document for citation in result.citations
    )
    row: EvaluationRow = {
        "id": case["id"],
        "expected_outcome": case["expected_outcome"],
        "actual_outcome": result.decision.outcome.value,
        "outcome_match": outcome_match,
        "expected_document": expected_document,
        "evidence_match": evidence_match,
        "confidence": result.analysis.confidence,
        "sensitive_topics": result.analysis.sensitive_topics,
        "missing_information": result.analysis.missing_information,
        "top_retrieval_score": result.citations[0].score if result.citations else 0.0,
    }
    if judge and case.get("judge_draft", False):
        if result.suggested_reply is None:
            row["draft_quality_pass"] = False
            row["draft_quality_error"] = (
                "No draft was generated for a fixture marked for draft-quality evaluation."
            )
        else:
            assessment = judge.assess(ticket, result.citations, result.suggested_reply)
            row["draft_quality_pass"] = passes_draft_quality(assessment)
            row["draft_quality"] = assessment.model_dump() | {"total_score": assessment.total_score}
    return row


def summarize(rows: list[EvaluationRow], execution_mode: str, judge_drafts: bool) -> dict[str, Any]:
    """Convert individual fixture results into gate metrics and final pass/fail status."""
    total = len(rows)
    outcome_matches = sum(int(row["outcome_match"]) for row in rows)
    evidence_matches = sum(int(row["evidence_match"]) for row in rows)
    judged_rows = [row for row in rows if "draft_quality_pass" in row]
    judged_draft_count = len(judged_rows)
    draft_quality_matches = sum(int(row["draft_quality_pass"]) for row in judged_rows)

    # A zero judged-draft count is valid only when judging was intentionally skipped.
    draft_quality_passed = not judge_drafts or (
        judged_draft_count > 0 and draft_quality_matches == judged_draft_count
    )
    passed = outcome_matches == total and evidence_matches == total and draft_quality_passed
    return {
        "status": "passed" if passed else "failed",
        "execution_mode": execution_mode,
        "total_cases": total,
        "routing_accuracy": round(outcome_matches / total, 3),
        "expected_document_recall": round(evidence_matches / total, 3),
        "judged_draft_count": judged_draft_count,
        "draft_quality_pass_rate": (
            round(draft_quality_matches / judged_draft_count, 3) if judged_draft_count else None
        ),
        "cases": rows,
    }


def print_report(report: dict[str, Any], as_json: bool, judge_drafts: bool) -> None:
    """Render either a machine-readable report or a concise terminal summary."""
    if as_json:
        print(json.dumps(report, indent=2))
        return

    total = report["total_cases"]
    outcome_matches = sum(int(row["outcome_match"]) for row in report["cases"])
    evidence_matches = sum(int(row["evidence_match"]) for row in report["cases"])
    marker = "PASS" if report["status"] == "passed" else "FAIL"
    print(
        f"{marker} [{report['execution_mode']}]: "
        f"{outcome_matches}/{total} routing outcomes and "
        f"{evidence_matches}/{total} expected-document checks passed."
    )
    if judge_drafts:
        judged = report["judged_draft_count"]
        passed = sum(
            int(row["draft_quality_pass"]) for row in report["cases"] if "draft_quality_pass" in row
        )
        print(f"  Draft-quality gate: {passed}/{judged} judged drafts passed.")
    for row in report["cases"]:
        checks_pass = (
            row["outcome_match"] and row["evidence_match"] and row.get("draft_quality_pass", True)
        )
        marker = "PASS" if checks_pass else "FAIL"
        print(
            f"  {marker}  {row['id']} -> {row['actual_outcome']} "
            f"(expected {row['expected_outcome']})"
        )
        if row.get("draft_quality_pass") is False and row.get("draft_quality"):
            quality = row["draft_quality"]
            print(
                "        Draft quality: "
                f"grounding={quality['grounding']}, "
                f"helpfulness={quality['helpfulness']}, "
                f"tone={quality['tone']}, "
                f"safety={quality['safety']}, "
                f"total={quality['total_score']}/8"
            )
            if quality["unsupported_claims"]:
                print("        Unsupported claims: " + "; ".join(quality["unsupported_claims"]))
            print(f"        Improvement: {quality['improvement_note']}")
        if row.get("draft_quality_error"):
            print(f"        Draft quality: {row['draft_quality_error']}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate routing, retrieval, and draft quality against synthetic ticket fixtures."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("evals/cases/support_tickets.json"),
    )
    parser.add_argument(
        "--case",
        dest="case_ids",
        action="append",
        help="Run one named case; repeat the option to run several cases.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the complete evaluation report as JSON.",
    )
    parser.add_argument(
        "--no-judge-drafts",
        action="store_true",
        help="Skip the default LLM-as-a-judge draft-quality gate in AI mode.",
    )
    args = parser.parse_args()
    settings = get_settings()
    judge_drafts = settings.execution_mode == "ai" and not args.no_judge_drafts
    cases = load_cases(args.dataset, args.case_ids, settings.execution_mode)

    initialize_database()
    judge = DraftQualityJudge(settings) if judge_drafts else None
    with SessionLocal() as session:
        rows = [evaluate_case(session, case, settings, judge) for case in cases]

    report = summarize(rows, settings.execution_mode, judge_drafts)
    print_report(report, args.json, judge_drafts)
    if report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
