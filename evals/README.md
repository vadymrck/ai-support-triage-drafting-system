# Evaluation Fixtures

This directory holds synthetic, version-controlled golden cases for workflow regression testing.

- `cases/support_tickets.json` defines the support tickets, expected final outcomes, and expected knowledge-base documents.
- `scripts/evaluate.py` runs the complete ticket-processing workflow against these fixtures.

Each fixture has a `modes` field. Shared safety and policy cases use `["deterministic", "ai"]`; semantic-retrieval or generated-draft cases can use `["ai"]` only. The evaluator automatically skips cases that do not apply to `EXECUTION_MODE`.

Use the full suite after changes to policy, prompts, PDF content, chunking, or retrieval. Use `--case <id>` to debug a single scenario.
