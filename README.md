# AI Support Triage & Drafting System

> A human-approved support workflow that classifies Zendesk tickets, retrieves grounded answers from PDF knowledge, and prepares internal triage context or a suggested response.

**Portfolio project — planned.** All future tickets, knowledge-base documents, and Zendesk data will be synthetic.

## Why this exists

Support teams repeatedly interpret incoming tickets, locate relevant internal guidance, decide whether a request is safe to handle normally, and draft similar replies. This project demonstrates a bounded, auditable way to automate that first layer without automating customer communication.

## Scope agreed for version 1

- Receive Zendesk ticket events through a direct webhook integration.
- Use a Python/FastAPI service as the application boundary and workflow orchestrator.
- Ingest synthetic PDF knowledge-base documents into PostgreSQL with pgvector.
- Use LLM structured outputs to classify tickets and extract decision-relevant signals.
- Retrieve relevant PDF passages and generate source-grounded support context.
- Apply deterministic Python policy rules to select the final outcome.
- Write the resulting support package to a private Zendesk agent note.
- Keep every customer reply under human control; the system never posts a public reply.
- Persist a decision trace for auditability and evaluation.

## Final outcomes

| Outcome | Meaning | Zendesk result |
| --- | --- | --- |
| `draft_ready` | The request is understood, permitted by policy, and sufficiently grounded in retrieved documentation. | Private note with an internal summary, cited sources, and a suggested reply for an agent to review and send manually. |
| `review_required` | The request is sensitive, urgent, ambiguous, low-confidence, or otherwise restricted by policy. | Private note with an internal triage brief, escalation reason, and recommended next action. No customer-facing draft. |
| `needs_knowledge_update` | The request is valid, but the knowledge base does not provide adequate or consistent support. | Private note that identifies the evidence gap and recommended knowledge-owner action. No customer-facing draft. |

## Architecture

```text
Zendesk ticket created or updated
        │ webhook (ngrok only for live local verification)
        ▼
FastAPI service
        ├── validates event and fetches ticket details through Zendesk API
        ├── obtains structured LLM analysis
        ├── retrieves relevant PDF chunks from PostgreSQL + pgvector
        ├── applies deterministic policy rules
        ├── persists the decision trace
        └── posts a private Zendesk agent note
                  │
                  ▼
          Human agent reviews and sends any public response
```

The FastAPI application owns integration, retrieval, decisioning, and audit persistence. The LLM reports validated observations; it does not determine the final outcome. A pure Python policy module makes the final routing decision and can be tested independently.

## Planned stack

- Python 3.12, FastAPI, Pydantic v2
- PostgreSQL + pgvector
- SQLAlchemy and Alembic
- OpenAI API for embeddings and structured output generation
- PDF parsing with page-level source metadata
- Zendesk API and webhooks
- Docker Compose, pytest, and a synthetic evaluation dataset
- ngrok for optional live Zendesk webhook verification from a local environment

## Local and GitHub-ready operation

The application, database, PDF ingestion, tests, and evaluation suite will run locally with Python and Docker Compose. Zendesk remains an optional external integration used to verify the live workflow with a trial account; it is not required to run the local services or test the core logic.

`EXECUTION_MODE=deterministic` uses local heuristics, lexical retrieval, and a template draft without OpenAI calls. `EXECUTION_MODE=ai` uses OpenAI for structured analysis, embeddings, and grounded draft generation. Both modes use the same deterministic routing policy.

AI-mode evaluations include an evaluation-only LLM draft-quality judge by default. Use `docker compose exec api python scripts/evaluate.py --no-judge-drafts` for the faster routing-and-retrieval-only run. See the [evaluation plan](docs/evaluation.md) for the rubric and deterministic pass gate.

## Continuous integration

The [AI quality workflow](.github/workflows/ai-quality.yml) runs on every push to `main`, including merged pull requests. It starts fresh Docker services, runs unit tests, ingests the shipped PDFs with AI embeddings, and runs the full AI evaluation (including the default draft-quality gate). Version-controlled Git hooks run `docker compose exec -T api pytest -q` before every local commit and push after one-time installation: `./scripts/install_git_hooks.sh`.

Add `OPENAI_API_KEY` as a repository Actions secret before enabling the workflow. It is intentionally not triggered for open pull requests, so API-backed evaluation runs only on trusted `main` code.

The published repository will include synthetic PDFs and ticket fixtures, `.env.example`, Docker setup, migrations, automated tests, an evaluation dataset, and Zendesk configuration instructions. It will not include secrets, customer data, or automatic customer-reply behavior.

## Documentation

- [Project brief](docs/project-brief.md)
- [Architecture and integration boundary](docs/architecture.md)
- [Decision policy](docs/decision-policy.md)
- [Local setup and Zendesk verification](docs/setup.md)
- [Evaluation plan](docs/evaluation.md)
