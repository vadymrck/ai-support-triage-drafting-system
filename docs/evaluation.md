# Evaluation Plan

## Purpose

The project evaluates the actual workflow rather than relying on a visually convincing single demo. The initial dataset is intentionally small and synthetic; it is a regression suite, not evidence of production performance.

## Dataset

`evals/cases/support_tickets.json` contains controlled tickets covering:

- a safe, grounded SSO request
- a safe, grounded billing/invoice request
- a privacy deletion request requiring review
- a payment dispute requiring review
- a valid request missing from the knowledge base

Each case defines an expected business outcome and, where applicable, the expected PDF document.

## Execution profiles

Each fixture declares which profiles can run it through a `modes` array:

```json
"modes": ["deterministic", "ai"]
```

Use both profiles for business-critical policy behavior, such as privacy, payment disputes, and customer escalation. Use `"modes": ["ai"]` for semantic-paraphrase retrieval or generated-draft cases that the deterministic keyword fallback should not be expected to solve. The evaluator skips fixtures that do not apply to the active `EXECUTION_MODE`.

## Metrics

| Metric | Definition | Initial use |
| --- | --- | --- |
| Routing accuracy | Final policy outcome equals the expected outcome. | Detect policy, classification, or threshold regressions. |
| Expected-document recall | The expected PDF appears in the retrieved evidence. | Detect retrieval or ingestion regressions. |
| Citation grounding | A `draft_ready` answer can be traced to retrieved passages. | Manual review initially; automate later with a bounded LLM-as-judge rubric. |
| Unsafe draft escape rate | Sensitive or uncertain cases that incorrectly return `draft_ready`. | Must be zero for the synthetic safety cases. |

## Running the evaluation

After generating and ingesting the synthetic PDFs:

```zsh
docker compose exec api python scripts/evaluate.py
```

The command returns non-zero if routing or expected-document checks fail. Run it after changes to prompts, PDF chunking, retrieval thresholds, or policy rules.

The default terminal output shows a clear `PASS` or `FAIL` summary. Add `--json` to print the complete machine-readable report instead.

To debug one scenario, pass its `id` from `evals/cases/support_tickets.json`:

```zsh
docker compose exec api python scripts/evaluate.py --case privacy-review
```

Repeat `--case` to run a small subset. Without it, the full regression dataset runs.

## Deliberate limitation

`EXECUTION_MODE=deterministic` supports local development without an API key; it is not an LLM-quality evaluation. The portfolio evaluation should be rerun with `EXECUTION_MODE=ai` and recorded only after inspecting the synthetic results.
