# Project Brief

## Objective

Build a small, credible support-assist application that turns an incoming HubSpot ticket into an auditable support package: structured ticket context, evidence from a PDF knowledge base, and either a human-reviewable draft or a clear escalation path.

## Business problem

Support teams spend time repeatedly reading unstructured tickets, determining their urgency and intent, searching documentation, and composing similar answers. A useful automation must improve speed without turning uncertain, sensitive, or unsupported answers into customer communication.

## Core input

A HubSpot ticket event and its full ticket details, such as:

> “I cannot sign in after our company enabled SSO this morning. Our entire finance team is blocked. Can you reset the setup?”

## Core output

An internal HubSpot note and persisted audit record containing:

- ticket classification, urgency, sentiment, and required action
- extracted policy-relevant signals and model confidence
- retrieved PDF citations with document and page references
- final policy outcome and explanation
- internal support summary
- suggested customer reply only when the outcome is `draft_ready`
- recommended owner or next step

## Non-goals

- Automatically sending public customer replies
- Replacing HubSpot or building a ticketing user interface
- Building a general-purpose chatbot or autonomous agent
- Using real customer tickets or proprietary support documentation
- Using n8n as the core orchestration layer
- Claiming measured time savings before a real deployment

## Evidence to produce

- Synthetic HubSpot ticket scenarios for all three final outcomes
- Synthetic PDF knowledge base with page-level citations
- Unit tests for policy rules and validation
- Integration tests for ticket processing and audit records
- Evaluation fixtures measuring routing accuracy, retrieval Recall@k, and optional LLM-as-a-judge draft quality with a deterministic pass gate
- Screenshots and a short walkthrough only after the end-to-end flow works
