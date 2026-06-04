# Connectors - Discover and Score Integrations from External Platforms

Connectors sync OAuth/app data from external SaaS platforms into SaaSShadow, run the risk pipeline on each integration, and persist results in scan history. No manual export scripts are required.

Community Edition ships two connectors: **Microsoft Entra** and **Slack**.

---

## Overview

| Connector | What it does | Auth |
|-----------|--------------|------|
| **Entra** | Lists app registrations from Microsoft Graph; each app's `requiredResourceAccess` and credential metadata are scanned. | Client credentials (tenant_id, client_id, client_secret) |
| **Slack** | Uses a bot or user token to identify the app via `auth.test` and reads scopes from the response header; one integration is scanned. | Bot token (xoxb-*) or user token (xoxp-*) |

Sync is **on-demand** via `POST /connectors/entra/sync` and `POST /connectors/slack/sync`. Results are written to the same scan history as `POST /scan/analyze`.

---

## Microsoft Entra (Azure AD)

**Endpoint:** `POST /connectors/entra/sync`

**Request body:**
```json
{
  "tenant_id": "your-tenant-guid",
  "client_id": "app-registration-client-id",
  "client_secret": "client-secret-value",
  "customer_id": "optional-tenant-tag"
}
```

**Prerequisites:**
- An app registration in Entra with **Application.Read.All** (application permission) or **Application.Read.All** (delegated). Grant admin consent for application permissions.
- Use the same app's **tenant ID**, **client (application) ID**, and **client secret** in the request.

**Flow:**
1. SaaSShadow obtains an access token via OAuth2 client credentials (`https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token`).
2. It calls `GET https://graph.microsoft.com/v1.0/applications?$select=id,displayName,appId,requiredResourceAccess,passwordCredentials&$top=999` and follows `@odata.nextLink` for pagination.
3. For each application, it builds a payload that includes `requiredResourceAccess` (so the existing Entra manifest parser can compute OAuth scope risk) and redacted credential metadata (no secret values).
4. The pipeline runs for each app; reports are persisted to scan history with `target` like `entra_{appId}`.

---

## Slack

**Endpoint:** `POST /connectors/slack/sync`

**Request body:**
```json
{
  "token": "xoxb-your-bot-token",
  "customer_id": "optional-tag"
}
```

**Prerequisites:**
- A Slack app with a **bot token** (recommended) or **user token**. The token is sent to Slack's API; do not expose it in logs or client-side code.

**Flow:**
1. SaaSShadow calls `POST https://slack.com/api/auth.test` with `Authorization: Bearer {token}`.
2. It reads the response body (team, user, bot_id, etc.) and the **x-oauth-scopes** response header (comma-separated scopes).
3. It builds one integration record: `source_app: "slack"`, `oauth.scopes` from the header, and minimal credential metadata.
4. The pipeline runs once; the report is stored with a `target` like `slack_{team_id}_{bot_id}`.

Note: Slack's `apps.permissions.info` API is deprecated. Scopes are taken from the `x-oauth-scopes` header on `auth.test` (and other Web API responses).

---

## Response shape

Both sync endpoints return the same structure:

```json
{
  "connector": "entra",
  "synced": 5,
  "scans": [
    { "scan_id": "uuid", "target": "entra_...", "risk_score": 42.5 },
    ...
  ],
  "errors": []
}
```

- **synced:** Number of integrations successfully scanned and stored.
- **scans:** One object per stored scan (`scan_id`, `target`, `risk_score`).
- **errors:** List of error messages (e.g. auth failure, per-app failures). Sync may still return `synced >= 0` if some apps succeed and others fail.

---

## Listing connectors

**Endpoint:** `GET /connectors`

Returns the list of available connectors (id, name, description) for UI or automation.

---

## Security notes

- **Entra:** Send `client_secret` only over HTTPS. Prefer environment variables or a secrets manager; avoid logging or storing the body.
- **Slack:** Treat the token as a secret; use HTTPS and restrict access to the sync endpoint (e.g. API key or network policy).
- Connector credentials are not persisted by SaaSShadow; they are used only for the duration of the sync request.
