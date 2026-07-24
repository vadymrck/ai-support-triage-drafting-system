# Decision Policy

## Principle

The LLM may interpret ticket text but does not decide the customer-handling outcome. The FastAPI service validates the structured model output, supplements it with deterministic high-precision sensitive-topic markers, considers retrieval evidence, and uses deterministic Python rules to select exactly one business outcome.

## Candidate signals

- issue type and affected product area
- urgency and blocker indicators
- customer sentiment
- sensitive-topic flags: security, privacy, account deletion, payment dispute, legal request, abuse, or account access risk
- model extraction confidence
- retrieval score and evidence sufficiency
- contradictory or missing documentation signals

## Routing rules

The policy evaluates rules in this order. A human-review rule always overrides retrieval quality.

### `review_required`

This outcome overrides all other paths when the ticket involves a sensitive topic, potential security incident, account compromise, privacy/deletion request, payment dispute, legal issue, abusive escalation, high-friction escalation language, critical blocker, model confidence below `0.70`, or insufficient information to understand the request.

The service creates an internal brief and escalation recommendation. It does not create a customer-facing draft.

### `needs_knowledge_update`

Use this outcome when the ticket is safe to handle but retrieval does not return adequate, relevant, and consistent support guidance. The current demo requires at least one retrieved chunk and a best retrieval score of `0.40` or higher before a ticket can become `draft_ready`. Examples include a new product behavior absent from the PDF knowledge base or conflicting document versions.

The service identifies the knowledge gap and suggested owner/action. It does not create a customer-facing draft.

### `draft_ready`

Use this outcome only when the ticket is non-sensitive, the classification is reliable, and the retrieved PDF passages adequately support an answer. The draft must be grounded in the cited passages and clearly marked as a suggested reply.

The service posts the support package as an internal HubSpot note. A human agent must review, edit as needed, and manually send any public response.

## Retrieval-score calibration

`top_retrieval_score` is the score of the highest-ranked knowledge-base chunk for a ticket. Higher is more relevant. In `EXECUTION_MODE=ai`, the score is `1 - cosine distance` between OpenAI embeddings. In `EXECUTION_MODE=deterministic`, it is a keyword-overlap score. Both currently use the same `0.40` draft-readiness floor for this small synthetic demo.

The number is not a universal quality grade and is not directly comparable across the two execution modes. It is a policy setting that must be recalibrated after changes to the knowledge base, chunking strategy, retrieval approach, or embedding model. The evaluation suite checks final routing and expected-document presence; it does not currently assert a minimum score per fixture.

## Technical exception path

Processing failures such as an unavailable model provider, database error, or HubSpot API failure are operational errors rather than business outcomes. They will be logged and retried or surfaced for investigation; they must never create a public response.
