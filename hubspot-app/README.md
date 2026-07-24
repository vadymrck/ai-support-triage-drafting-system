# HubSpot Configuration App

This private HubSpot developer app provides version-controlled integration configuration for the portfolio demo.

## Purpose

- Request the smallest CRM scope set needed to read tickets and create internal notes.
- Define an inactive ticket-created webhook subscription.
- Keep the temporary ngrok URL and active subscription out of version control.

## Deployment boundary

Upload this app from the main HubSpot developer account, then install it only into the isolated `AI Support Triage Demo` developer test account. The installed app supplies a static access token and client secret. Both remain local-only values in the project root `.env` file.

## Live-demo sequence

1. Validate and upload from this directory with the HubSpot CLI.
2. Install the private app into the developer test account.
3. In HubSpot, replace the placeholder target URL with the current ngrok URL plus `/v1/webhooks/hubspot`, then activate the ticket-created subscription.
4. Set `HUBSPOT_PRIVATE_APP_ACCESS_TOKEN` and `HUBSPOT_PRIVATE_APP_CLIENT_SECRET` in the project root `.env`.
5. Keep `HUBSPOT_NOTE_SYNC_ENABLED=false` for the first live read-and-decision check. Enable it only for the final internal-note verification.

Do not commit secrets, static access tokens, client secrets, or an ngrok URL.
