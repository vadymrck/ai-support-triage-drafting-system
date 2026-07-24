# Local Setup and HubSpot Verification

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

`.github/workflows/ai-quality.yml` runs on a push to `main` (including a merged pull request) or through a manual GitHub Actions run. Each run starts a fresh Docker database, runs Ruff lint/format checks, runs unit tests, ingests the repository PDFs with AI embeddings, then runs the default full AI evaluation.

Before pushing this project to GitHub, create a repository Actions secret named `OPENAI_API_KEY`. The workflow does not run on open pull requests, keeping API-backed evaluation limited to trusted main-branch code.

Version-controlled Git hooks run Ruff lint and format checks before every local commit, and the unit suite before every local push. Enable them once after cloning:

```zsh
./scripts/install_git_hooks.sh
```

The hooks run inside the Docker API service. You can run the checks directly whenever needed:

```zsh
docker compose exec -T api ruff check .
docker compose exec -T api ruff format --check .
docker compose exec -T api pytest -q
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

## HubSpot verification

HubSpot is used only to validate the real integration and capture portfolio evidence. Use a dedicated developer test account, never a real support portal.

1. Validate and upload the version-controlled [HubSpot configuration app](../hubspot-app/) from the main developer account, then install it into the `AI Support Triage Demo` developer test account. It requests the ticket and note-write scopes and ships with an inactive ticket-created subscription. Keep its static access token and client secret local only.
2. Set these values in `.env`:

   ```dotenv
   HUBSPOT_PRIVATE_APP_ACCESS_TOKEN=...
   HUBSPOT_PRIVATE_APP_CLIENT_SECRET=...
   HUBSPOT_WEBHOOK_BASE_URL=https://YOUR-NGROK-DOMAIN
   HUBSPOT_NOTE_SYNC_ENABLED=false
   ```

   Keep note sync disabled for the first request. This permits a live read-and-decision check without writing to HubSpot.

3. Start an HTTPS tunnel to the local API, for example:

   ```zsh
   ngrok http 8000
   ```

4. Configure the private app's webhook target URL as:

   ```text
   https://YOUR-NGROK-DOMAIN/v1/webhooks/hubspot
   ```

5. Subscribe to the HubSpot ticket creation event. Optionally add the ticket-property-change event later, after filtering the property to avoid reprocessing every edit.
6. The service validates `X-HubSpot-Signature-V3` and `X-HubSpot-Request-Timestamp`, rejects stale requests, parses HubSpot's batched event payload, and deduplicates by HubSpot `eventId`.
7. Create one synthetic ticket in the test account. You can use the HubSpot UI, or the included helper (it reads the local token and never prints it):

   ```zsh
   docker compose exec api python scripts/create_hubspot_demo_ticket.py \
     --subject "Cannot access SSO" \
     --description "I cannot sign in through SSO. Please help me regain access."
   ```

   Confirm its decision record locally, then set `HUBSPOT_NOTE_SYNC_ENABLED=true` and repeat with a new ticket to verify the internal note.

The HubSpot adapter reads ticket details and writes internal notes only. It contains no code path for sending a customer message or publishing a public reply.
