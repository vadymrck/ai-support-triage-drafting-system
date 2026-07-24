import json

import pytest

from scripts.evaluate import load_cases, print_report, summarize


def test_load_cases_filters_by_requested_id_and_execution_mode(tmp_path) -> None:
    dataset = tmp_path / "cases.json"
    dataset.write_text(
        json.dumps(
            [
                {"id": "shared", "modes": ["deterministic", "ai"]},
                {"id": "ai-only", "modes": ["ai"]},
            ]
        )
    )

    cases = load_cases(dataset, ["shared", "ai-only"], "deterministic")

    assert [case["id"] for case in cases] == ["shared"]


def test_load_cases_rejects_unknown_id(tmp_path) -> None:
    dataset = tmp_path / "cases.json"
    dataset.write_text(json.dumps([{"id": "known", "modes": ["ai"]}]))

    with pytest.raises(SystemExit, match="Unknown evaluation case ID\\(s\\): missing"):
        load_cases(dataset, ["missing"], "ai")


def test_default_ai_quality_gate_fails_when_no_drafts_were_judged() -> None:
    report = summarize(
        [
            {
                "outcome_match": True,
                "evidence_match": True,
            }
        ],
        execution_mode="ai",
        judge_drafts=True,
    )

    assert report["status"] == "failed"
    assert report["judged_draft_count"] == 0


def test_intentionally_skipped_judge_allows_routing_and_retrieval_pass() -> None:
    report = summarize(
        [
            {
                "outcome_match": True,
                "evidence_match": True,
            }
        ],
        execution_mode="deterministic",
        judge_drafts=False,
    )

    assert report["status"] == "passed"


def test_human_report_includes_failed_draft_quality_details(capsys) -> None:
    report = {
        "status": "failed",
        "execution_mode": "ai",
        "total_cases": 1,
        "judged_draft_count": 1,
        "cases": [
            {
                "id": "draft-case",
                "actual_outcome": "draft_ready",
                "expected_outcome": "draft_ready",
                "outcome_match": True,
                "evidence_match": True,
                "draft_quality_pass": False,
                "draft_quality": {
                    "grounding": 1,
                    "helpfulness": 2,
                    "tone": 2,
                    "safety": 2,
                    "total_score": 7,
                    "unsupported_claims": ["Unsupported action claim."],
                    "improvement_note": "Remove the unsupported claim.",
                },
            }
        ],
    }

    print_report(report, as_json=False, judge_drafts=True)

    output = capsys.readouterr().out
    assert "FAIL  draft-case" in output
    assert "Draft quality: grounding=1" in output
    assert "Unsupported claims: Unsupported action claim." in output
    assert "Improvement: Remove the unsupported claim." in output
