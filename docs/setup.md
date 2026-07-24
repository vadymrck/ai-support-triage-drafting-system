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

## Model configuration

`OPENAI_MODEL` and `OPENAI_JUDGE_MODEL` are runtime configuration: values in `.env` (or deployment environment variables) override the safe fallback defaults in `app/config.py`. The project does not place model names in individual service calls.

The standard setup uses `gpt-5-mini` for ticket analysis and drafting, and `gpt-5.6-terra` only for the optional, asynchronous draft-quality judge. This intentionally separates generation from evaluation. `text-embedding-3-small` remains the embedding model. For a new environment, copy `.env.example` to `.env` and edit the model variables there only when an explicit override is required.

## GitHub Actions evaluation

`.github/workflows/ai-quality.yml` runs on a push to `main` (including a merged pull request) or through a manual GitHub Actions run. Each run starts a fresh Docker database, runs unit tests first, ingests the repository PDFs with AI embeddings, then runs the default full AI evaluation.

Before pushing this project to GitHub, create a repository Actions secret named `OPENAI_API_KEY`. The workflow does not run on open pull requests, keeping API-backed evaluation limited to trusted main-branch code.

Local commits and pushes do not run tests automatically because this project intentionally has no Git hook. Run the fast local check manually before committing or pushing:

```zsh
docker compose exec api pytest -q
```

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
