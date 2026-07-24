import json

import pytest

from scripts.evaluate import load_cases, summarize


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
