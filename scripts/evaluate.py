import argparse
import json
from pathlib import Path

from app.config import get_settings
from app.database import SessionLocal, initialize_database
from app.schemas import TicketInput
from app.services import process_ticket


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate routing and retrieval against synthetic ticket fixtures.")
    parser.add_argument("--dataset", type=Path, default=Path("evals/cases/support_tickets.json"))
    parser.add_argument("--case", dest="case_ids", action="append", help="Run one named case; repeat the option to run several cases.")
    parser.add_argument("--json", action="store_true", help="Print the complete evaluation report as JSON.")
    args = parser.parse_args()
    cases = json.loads(args.dataset.read_text())
    if args.case_ids:
        requested_ids = set(args.case_ids)
        cases = [case for case in cases if case["id"] in requested_ids]
        found_ids = {case["id"] for case in cases}
        missing_ids = requested_ids - found_ids
        if missing_ids:
            raise SystemExit(f"Unknown evaluation case ID(s): {', '.join(sorted(missing_ids))}")
    initialize_database()
    outcome_matches = 0
    evidence_matches = 0
    rows = []
    with SessionLocal() as session:
        for case in cases:
            result = process_ticket(session, TicketInput(**case["ticket"]), get_settings())
            outcome_match = result.decision.outcome.value == case["expected_outcome"]
            expected_document = case["expected_document"]
            evidence_match = expected_document is None or any(citation.document_title == expected_document for citation in result.citations)
            outcome_matches += outcome_match
            evidence_matches += evidence_match
            rows.append({
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
            })
    total = len(cases)
    passed = outcome_matches == total and evidence_matches == total
    report = {"status": "passed" if passed else "failed", "total_cases": total, "routing_accuracy": round(outcome_matches / total, 3), "expected_document_recall": round(evidence_matches / total, 3), "cases": rows}
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"{'PASS' if passed else 'FAIL'}: {outcome_matches}/{total} routing outcomes and {evidence_matches}/{total} expected-document checks passed.")
        for row in rows:
            marker = "PASS" if row["outcome_match"] and row["evidence_match"] else "FAIL"
            print(f"  {marker}  {row['id']} -> {row['actual_outcome']} (expected {row['expected_outcome']})")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
