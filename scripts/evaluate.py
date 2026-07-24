import argparse
import json
from pathlib import Path

from app.config import get_settings
from app.database import SessionLocal, initialize_database
from app.judging import DraftQualityJudge, passes_draft_quality
from app.schemas import TicketInput
from app.services import process_ticket


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate routing, retrieval, and optional draft quality against synthetic ticket fixtures.")
    parser.add_argument("--dataset", type=Path, default=Path("evals/cases/support_tickets.json"))
    parser.add_argument("--case", dest="case_ids", action="append", help="Run one named case; repeat the option to run several cases.")
    parser.add_argument("--json", action="store_true", help="Print the complete evaluation report as JSON.")
    parser.add_argument("--no-judge-drafts", action="store_true", help="Skip the default LLM-as-a-judge draft-quality gate in AI mode.")
    args = parser.parse_args()
    all_cases = json.loads(args.dataset.read_text())
    execution_mode = get_settings().execution_mode
    judge_drafts = execution_mode == "ai" and not args.no_judge_drafts
    if args.case_ids:
        requested_ids = set(args.case_ids)
        found_ids = {case["id"] for case in all_cases}
        missing_ids = requested_ids - found_ids
        if missing_ids:
            raise SystemExit(f"Unknown evaluation case ID(s): {', '.join(sorted(missing_ids))}")
        all_cases = [case for case in all_cases if case["id"] in requested_ids]
    cases = [case for case in all_cases if execution_mode in case.get("modes", ["deterministic", "ai"])]
    if not cases:
        requested = ", ".join(args.case_ids) if args.case_ids else "the dataset"
        raise SystemExit(f"No evaluation cases from {requested} apply to EXECUTION_MODE={execution_mode}.")
    initialize_database()
    outcome_matches = 0
    evidence_matches = 0
    draft_quality_matches = 0
    judged_draft_count = 0
    rows = []
    judge = DraftQualityJudge(get_settings()) if judge_drafts else None
    with SessionLocal() as session:
        for case in cases:
            result = process_ticket(session, TicketInput(**case["ticket"]), get_settings())
            outcome_match = result.decision.outcome.value == case["expected_outcome"]
            expected_document = case["expected_document"]
            evidence_match = expected_document is None or any(citation.document_title == expected_document for citation in result.citations)
            outcome_matches += outcome_match
            evidence_matches += evidence_match
            row = {
                "id": case["id"],
                "expected_outcome": case["expected_outcome"],
                "actual_outcome": result.decision.outcome.value,
                "outcome_match": outcome_match,
                "expected_document": expected_document,
                "evidence_match": evidence_match,
                "confidence": result.analysis.confidence,
                "sensitive_topics": result.analysis.sensitive_topics,
                "missing_information": result.analysis.missing_information,
                "top_retrieval_score": result.citations[0].score if result.citations else 0,
            }
            if judge and case.get("judge_draft", False):
                judged_draft_count += 1
                if result.suggested_reply is None:
                    row["draft_quality_pass"] = False
                    row["draft_quality_error"] = "No draft was generated for a fixture marked for draft-quality evaluation."
                else:
                    assessment = judge.assess(TicketInput(**case["ticket"]), result.citations, result.suggested_reply)
                    quality_pass = passes_draft_quality(assessment)
                    draft_quality_matches += quality_pass
                    row["draft_quality_pass"] = quality_pass
                    row["draft_quality"] = assessment.model_dump() | {"total_score": assessment.total_score}
            rows.append(row)
    total = len(cases)
    draft_quality_passed = draft_quality_matches == judged_draft_count
    passed = outcome_matches == total and evidence_matches == total and draft_quality_passed
    report = {"status": "passed" if passed else "failed", "execution_mode": execution_mode, "total_cases": total, "routing_accuracy": round(outcome_matches / total, 3), "expected_document_recall": round(evidence_matches / total, 3), "judged_draft_count": judged_draft_count, "draft_quality_pass_rate": round(draft_quality_matches / judged_draft_count, 3) if judged_draft_count else None, "cases": rows}
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"{'PASS' if passed else 'FAIL'} [{execution_mode}]: {outcome_matches}/{total} routing outcomes and {evidence_matches}/{total} expected-document checks passed.")
        if judge_drafts:
            print(f"  Draft-quality gate: {draft_quality_matches}/{judged_draft_count} judged drafts passed.")
        for row in rows:
            marker = "PASS" if row["outcome_match"] and row["evidence_match"] else "FAIL"
            print(f"  {marker}  {row['id']} -> {row['actual_outcome']} (expected {row['expected_outcome']})")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
