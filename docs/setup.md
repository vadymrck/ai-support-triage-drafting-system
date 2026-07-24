# Local Setup and Zendesk Verification

## Local runtime

1. Copy `.env.example` to `.env`.
2. Start the API and database:

   ```zsh
   docker compose up --build
   ```

3. Confirm that the service is running:

   ```zsh
   curl http://localhost:8000/health
   ```

4. The default `EXECUTION_MODE=deterministic` keeps policy and API development runnable without an LLM credential. Add `OPENAI_API_KEY` and set `EXECUTION_MODE=ai` when ready to use real structured analysis, embeddings, and grounded draft generation.

5. Ingest the synthetic PDFs included with the repository:

   ```zsh
   docker compose exec api python scripts/ingest_pdfs.py data/knowledge-base --replace
   docker compose exec api python scripts/evaluate.py
   ```

## Local ticket processing

Use the local endpoint while developing the workflow:

```zsh
curl -X POST http://localhost:8000/v1/tickets/process \
  -H 'Content-Type: application/json' \
  -d '{"ticket_id":1001,"subject":"Unable to sign in with SSO","description":"I cannot sign in after we enabled SSO."}'
```

The endpoint returns the complete support package. It never sends a customer-facing message.

## Zendesk verification

Zendesk is used only to validate the real integration and capture portfolio evidence. A trial account is sufficient.

1. Set `ZENDESK_SUBDOMAIN`, `ZENDESK_EMAIL`, `ZENDESK_API_TOKEN`, and `ZENDESK_WEBHOOK_SIGNING_SECRET` in `.env`.
2. Start an HTTPS tunnel to the local API, for example:

   ```zsh
   ngrok http 8000
   ```

3. Configure Zendesk to POST ticket events to:

   ```text
   https://YOUR-NGROK-DOMAIN/v1/webhooks/zendesk
   ```

4. Enable Zendesk webhook signing. The service validates `X-Zendesk-Webhook-Signature` and `X-Zendesk-Webhook-Signature-Timestamp`, rejects stale requests, and deduplicates by Zendesk invocation ID.
5. Set `ZENDESK_NOTE_SYNC_ENABLED=true` only after confirming that test tickets and private notes are configured correctly.

The Zendesk adapter only reads ticket details and writes private ticket comments. It contains no code path for publishing a public reply.
