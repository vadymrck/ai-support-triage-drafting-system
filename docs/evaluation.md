# Evaluation Plan

## Purpose

The project evaluates the actual workflow rather than relying on a visually convincing single demo. The initial dataset is intentionally small and synthetic; it is a regression suite, not evidence of production performance.

## Dataset

`evals/cases/support_tickets.json` contains controlled tickets covering:

- a safe, grounded SSO request
- a safe, grounded billing/invoice request
- a privacy deletion request requiring review
- a payment dispute requiring review
- a possible account-compromise report requiring review
- a legal notice requiring review
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
| Draft-quality gate | A selected `draft_ready` answer is assessed for grounding, helpfulness, tone, and safety. | Optional LLM-as-a-judge run; model observations are converted into a deterministic pass rule. |
| Unsafe draft escape rate | Sensitive or uncertain cases that incorrectly return `draft_ready`. | Must be zero for the synthetic safety cases. |

## Running the evaluation

After ingesting the synthetic PDFs:

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

## Test execution lifecycle

Version-controlled Git hooks run the fast unit suite before every local commit and push. Enable them once after cloning:

```zsh
./scripts/install_git_hooks.sh
```

The hooks run `docker compose exec -T api pytest -q` and require the Docker API service to be running.

The GitHub Actions workflow runs automatically only after a push to `main`, including a merged pull request. It uses a new Docker database for every run and executes this order:

1. `pytest` unit tests.
2. PDF ingestion in `EXECUTION_MODE=ai`, creating fresh embeddings in pgvector.
3. The default AI evaluation, including every applicable routing/retrieval fixture and opted-in draft-quality judge check.

The workflow needs the repository Actions secret `OPENAI_API_KEY`. It is also available as a manual GitHub Actions run. A regular push to another branch or an open pull request does not trigger it.

## Optional LLM-as-a-judge draft-quality gate

In AI mode, the default evaluation includes the draft-quality gate for selected `draft_ready` fixtures:

```zsh
docker compose exec api python scripts/evaluate.py
```

Use `--no-judge-drafts` for the faster routing-and-retrieval-only run:

```zsh
docker compose exec api python scripts/evaluate.py --no-judge-drafts
```

The gate is deliberately evaluation-only: it is not called when a real ticket is processed and cannot change the application's routing decision. Fixtures opt in with `"judge_draft": true`.

The judge receives only the synthetic ticket, retrieved excerpts, and proposed draft. It returns structured 0–2 scores for grounding, helpfulness, tone, and safety, plus unsupported claims and one improvement note. Code—not the judge—applies the pass rule: grounding must be `2`, safety must be `2`, and the total must be at least `7/8`. The evaluator fails when an opted-in draft does not meet that rule.

The gate runs only with `EXECUTION_MODE=ai`, an `OPENAI_API_KEY`, and makes additional model calls. It is skipped automatically in `EXECUTION_MODE=deterministic`, which remains a no-call development profile. In a default AI run, zero opted-in draft fixtures is a configuration failure; zero judged drafts is valid only when judging was deliberately skipped with `--no-judge-drafts` or by using deterministic mode. The judge uses the configured `OPENAI_JUDGE_MODEL` through the Responses API, separately from the application model that generated the draft. Its results should be treated as a regression signal, not as a substitute for human review of customer communications.

## Deliberate limitation

`EXECUTION_MODE=deterministic` supports local development without an API key; it is not an LLM-quality evaluation. The portfolio evaluation should be rerun with `EXECUTION_MODE=ai` and recorded only after inspecting the synthetic results.
