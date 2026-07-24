# Architecture and Integration Boundary

## Design choice

The application is FastAPI-first. Unlike the lead-intelligence project, a workflow automation platform is not the primary runtime. The project should demonstrate an application service with explicit data models, retrieval logic, deterministic policy code, database persistence, and automated tests.

## Runtime flow

```text
HubSpot
  │ ticket created or updated webhook
  ▼
FastAPI webhook endpoint
  │ validate payload, deduplicate event, fetch ticket details
  ▼
Ticket analysis service
  │ structured classification through LLM provider
  ▼
Retrieval service
  │ embed ticket query and retrieve PDF chunks from pgvector
  ▼
Policy service
  │ deterministic routing using validated analysis + retrieval evidence
  ├── draft_ready
  ├── review_required
  └── needs_knowledge_update
  ▼
Persistence and HubSpot adapter
  │ store audit trace and post an internal ticket note
  ▼
Human support agent
  │ reviews, edits, and sends any public customer response
```

## Local development and live verification

Docker Compose runs the FastAPI service and PostgreSQL with pgvector locally. The normal development loop uses synthetic ticket fixtures and automated tests.

For one live integration verification, a dedicated HubSpot developer test account can send its webhook to the local FastAPI service through an ngrok HTTPS tunnel. HubSpot is not emulated locally and is not required for core development. Credentials and tunnel URLs remain local environment configuration.

HubSpot can batch webhook events. The endpoint validates and acknowledges the batch before processing it in FastAPI background tasks, avoiding webhook timeouts during model calls. It parses only ticket events, deduplicates by HubSpot `eventId`, fetches the ticket by `objectId`, and writes a note only after decisioning succeeds. HubSpot v3 signature validation uses the HTTP method, full public webhook URL, raw request body, and timestamp; `HUBSPOT_WEBHOOK_BASE_URL` keeps that URL explicit when the API runs behind ngrok. A single private app supplies both the API token and its client secret.

## Knowledge ingestion

Synthetic PDFs are parsed into chunks that retain document title, version, page number, heading where available, and source text. Embeddings and metadata are stored in PostgreSQL/pgvector. Retrieved chunks must be included in the decision trace so each `draft_ready` suggestion remains traceable to its support guidance.

## Safety boundary

The LLM produces validated observations only: issue classification, urgency, sentiment, sensitive-topic flags, missing-information flags, and confidence. The Python policy module sets the final outcome. The service never calls a HubSpot customer-message endpoint; it creates internal notes only.
