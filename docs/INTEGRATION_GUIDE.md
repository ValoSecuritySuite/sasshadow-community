# Integration Guide - Extracting SaaS Configuration JSON

SaaSShadow.ai analyzes **integration configuration artifacts** - the OAuth grants, API tokens, webhook URLs, and data-mapping settings that connect one SaaS platform to another.

This guide explains **where to find those artifacts** for each major platform and **how to format them** for SaaSShadow analysis.

---

## What SaaSShadow Needs

Every integration you scan should be a JSON object with these fields:

```json
{
  "target": "descriptive_integration_name",
  "json_data": {
    "source_app": "platform_a",
    "destination_app": "platform_b",
    "oauth": {
      "scopes": ["scope.one", "scope.two"]
    },
    "credentials": {
      "access_token": "...",
      "expires_in_days": 90
    },
    "data_types": ["pii", "financial"]
  },
  "metadata": {
    "token_rotation_enabled": false
  }
}
```

| Field | Required | Purpose |
|---|---|---|
| `target` | Yes | Human-readable name for this integration |
| `json_data.source_app` | Recommended | Origin platform name |
| `json_data.destination_app` | Recommended | Destination platform name |
| `json_data.oauth.scopes` | If applicable | OAuth scopes as a list or space-separated string |
| `json_data.credentials.*` | If applicable | Any tokens, keys, or secrets present in the config |
| `json_data.data_types` | Recommended | What data moves: `pii`, `financial`, `credentials`, `customer_data`, `health` |
| `metadata.token_rotation_enabled` | Recommended | Whether the platform enforces token rotation |

SaaSShadow accepts flexibility - nested `oauth.scope`, `oauth.scopes`, `oauth_scopes`, and space-separated strings all work. Credentials can appear at any nesting depth; the scanner walks the full payload tree.

---

## Export JSON Directly from Platform APIs

Most platforms give you the exact JSON you need through their APIs or CLIs. You do **not** need to copy-paste values manually. Run the commands below, pipe the output into SaaSShadow, and you're done.

> **How it works:** Each command below calls the platform's own API to export the integration config as JSON. The output already contains the OAuth scopes, tokens, and credentials that SaaSShadow analyzes - you just wrap it in the SaaSShadow envelope and submit.

---

### Microsoft 365 / Azure AD

Azure AD exposes app registrations, permission grants, and service principals as JSON through both the CLI and the Microsoft Graph API.

**Get the full app registration (scopes, credentials, redirect URIs):**
```bash
# Returns JSON with appId, requiredResourceAccess (scopes), passwordCredentials, etc.
az ad app show --id <app-id> --output json > m365_app.json
```

**Get all OAuth permission grants for a service principal:**
```bash
# Returns JSON array: each grant has scope (space-separated), clientId, resourceId
az rest --method GET \
  --url "https://graph.microsoft.com/v1.0/oauth2PermissionGrants?\$filter=clientId eq '<service-principal-id>'" \
  --output json > m365_grants.json
```

**Get the current access token + metadata:**
```bash
# Returns JSON with accessToken, expiresOn, subscription, tenant
az account get-access-token --resource https://graph.microsoft.com --output json > m365_token.json
```

**Pipe it all directly into SaaSShadow:**
```bash
# One-liner: export app config and scan it immediately
az ad app show --id <app-id> -o json | \
  jq '{target: "m365_\(.appId)", json_data: {source_app: "microsoft365", oauth: {scopes: [.requiredResourceAccess[].resourceAccess[].id]}, credentials: .passwordCredentials}, metadata: {token_rotation_enabled: false}}' | \
  curl -s -X POST http://localhost:8000/scan/analyze -H "Content-Type: application/json" -d @-
```

---

### Google Workspace

Google Cloud Console stores OAuth client configs as downloadable JSON files, and the Admin SDK exposes user-granted token data.

**Download the OAuth client credentials JSON (this is the file Google gives you):**
```bash
# Google Cloud Console → APIs & Services → Credentials → your OAuth Client → Download JSON
# The downloaded file looks like:
# {"installed":{"client_id":"...","client_secret":"...","auth_uri":"...","token_uri":"...",...}}
```

**Export via gcloud CLI:**
```bash
# Get the current access token as JSON
gcloud auth print-access-token --format=json > google_token.json

# List service account keys (returns JSON with key IDs, creation dates)
gcloud iam service-accounts keys list \
  --iam-account=<sa-email>@<project>.iam.gserviceaccount.com \
  --format=json > google_sa_keys.json
```

**List all OAuth tokens granted by a specific user (Admin SDK):**
```bash
# Returns JSON array: each token has clientId, scopes[], displayText
curl -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  "https://admin.googleapis.com/admin/directory/v1/users/<user-email>/tokens" \
  > google_user_tokens.json
```

**The client_secrets.json file Google gives you is already JSON - scan it directly:**
```bash
cat client_secrets.json | \
  jq '{target: "google_workspace_integration", json_data: {source_app: "google_workspace", oauth: .installed, credentials: .installed}}' | \
  curl -s -X POST http://localhost:8000/scan/analyze -H "Content-Type: application/json" -d @-
```

---

### Salesforce

Salesforce Connected Apps expose their config through the Tooling API and the `sf` CLI.

**Export connected app metadata:**
```bash
# Returns JSON with oauthConfig (scopes), consumerKey, consumerSecret
sf org display --json > salesforce_org.json

# Tooling API - full connected app record
curl -H "Authorization: Bearer <access_token>" \
  "https://<instance>.salesforce.com/services/data/v59.0/tooling/query/?q=SELECT+Id,Name,OptionsFullContentPushNotifications+FROM+ConnectedApplication" \
  > salesforce_connected_apps.json
```

**Export the current OAuth token info:**
```bash
# Returns JSON with id, access_token, instance_url, token_type, issued_at
curl -H "Authorization: Bearer <access_token>" \
  "https://<instance>.salesforce.com/services/oauth2/userinfo" \
  > salesforce_token_info.json
```

---

### Slack

Slack gives you everything through its API - scopes, tokens, and app config are all JSON responses.

**Get your bot token's scopes and identity (the API tells you exactly what permissions are granted):**
```bash
# Returns JSON: ok, url, team, user, team_id, user_id, bot_id
# The response headers include X-OAuth-Scopes with the full scope list
curl -H "Authorization: Bearer xoxb-your-token" \
  https://slack.com/api/auth.test > slack_auth.json

# Get the bot token scopes explicitly
curl -H "Authorization: Bearer xoxb-your-token" \
  "https://slack.com/api/apps.permissions.info" > slack_scopes.json
```

**List all approved apps in your workspace (admin token required):**
```bash
# Returns JSON array of approved apps with scopes, tokens, last used dates
curl -H "Authorization: Bearer xoxp-admin-token" \
  "https://slack.com/api/admin.apps.approved.list" > slack_approved_apps.json
```

**Scan a Slack app directly:**
```bash
curl -H "Authorization: Bearer xoxb-your-token" https://slack.com/api/auth.test | \
  jq '{target: "slack_to_jira", json_data: {source_app: "slack", credentials: {bot_token: "xoxb-your-token"}, oauth: {scopes: .response_metadata.scopes}}, metadata: {token_rotation_enabled: false}}' | \
  curl -s -X POST http://localhost:8000/scan/analyze -H "Content-Type: application/json" -d @-
```

---

### GitHub

GitHub returns token scopes in API response headers and app configs as JSON.

**Check what scopes your token has (the API tells you in the response headers):**
```bash
# The X-OAuth-Scopes header in the response lists all granted scopes
curl -sI -H "Authorization: Bearer ghp_your_token" \
  https://api.github.com/rate_limit | grep -i x-oauth-scopes
```

**Export as JSON using the GitHub CLI:**
```bash
# Get token status and scopes
gh auth status --show-token 2>&1 | head -20

# List all GitHub App installations in your org (returns JSON)
gh api /orgs/{org}/installations > github_installations.json

# List all OAuth apps authorized by a user
gh api /applications/grants > github_oauth_grants.json
```

**Get a full app installation config:**
```bash
# Returns JSON with permissions, events, account, access_tokens_url
gh api /app/installations/<installation-id> > github_app_install.json
```

---

### AWS

AWS IAM access keys, role policies, and credential reports are all available as JSON through the CLI.

**Export access keys for a user:**
```bash
# Returns JSON: AccessKeyId, Status, CreateDate for each key
aws iam list-access-keys --user-name <integration-user> --output json > aws_keys.json
```

**Export the full role policy (what the integration can access):**
```bash
# Returns JSON: PolicyName, PolicyDocument with Statements, Actions, Resources
aws iam get-role-policy --role-name SaaSIntegrationRole --policy-name <policy> \
  --output json > aws_role_policy.json

# Or list all attached policies
aws iam list-attached-role-policies --role-name SaaSIntegrationRole \
  --output json > aws_attached_policies.json
```

**Generate a credential report (CSV → convert to JSON):**
```bash
aws iam generate-credential-report
aws iam get-credential-report --output json > aws_credential_report.json
```

**Check key age (rotation hygiene) and scan directly:**
```bash
aws iam list-access-keys --user-name <user> --output json | \
  jq '{target: "aws_to_datadog", json_data: {source_app: "aws", credentials: .AccessKeyMetadata[0]}, metadata: {token_rotation_enabled: false}}' | \
  curl -s -X POST http://localhost:8000/scan/analyze -H "Content-Type: application/json" -d @-
```

---

### Okta

Okta's Admin APIs return full app configs, scopes, and token metadata as JSON.

**List all apps and their credentials:**
```bash
# Returns JSON array: each app has credentials, settings, signOnMode, label
curl -H "Authorization: SSWS <api-token>" \
  "https://<your-domain>.okta.com/api/v1/apps" > okta_apps.json
```

**Get a specific app's config (scopes, client credentials, sign-on settings):**
```bash
curl -H "Authorization: SSWS <api-token>" \
  "https://<your-domain>.okta.com/api/v1/apps/<app-id>" > okta_app_config.json
```

**List scopes on an authorization server:**
```bash
curl -H "Authorization: SSWS <api-token>" \
  "https://<your-domain>.okta.com/api/v1/authorizationServers/<auth-server-id>/scopes" \
  > okta_scopes.json
```

**List active API tokens:**
```bash
curl -H "Authorization: SSWS <api-token>" \
  "https://<your-domain>.okta.com/api/v1/users/<user-id>/clients" \
  > okta_user_clients.json
```

---

### Stripe

Stripe's API returns webhook configs and key metadata as JSON.

**List all webhook endpoints (returns JSON with URL, enabled_events, secret):**
```bash
# Using Stripe CLI
stripe webhook_endpoints list --output json > stripe_webhooks.json

# Using the API
curl -u sk_live_your_key: \
  "https://api.stripe.com/v1/webhook_endpoints" > stripe_webhooks.json
```

**Get a specific webhook endpoint (includes the signing secret):**
```bash
curl -u sk_live_your_key: \
  "https://api.stripe.com/v1/webhook_endpoints/we_123456" > stripe_webhook_detail.json
```

---

### Jira / Atlassian Cloud

**List accessible resources and scopes for your token:**
```bash
# Returns JSON array: id, url, name, scopes
curl -H "Authorization: Bearer <access_token>" \
  "https://api.atlassian.com/oauth/token/accessible-resources" > jira_resources.json
```

**Get your own user info (verifies token works):**
```bash
curl -H "Authorization: Basic $(echo -n user@company.com:<api-token> | base64)" \
  "https://<site>.atlassian.net/rest/api/3/myself" > jira_myself.json
```

**List webhooks:**
```bash
curl -H "Authorization: Basic $(echo -n user@company.com:<api-token> | base64)" \
  "https://<site>.atlassian.net/rest/api/3/webhook" > jira_webhooks.json
```

---

### HubSpot

**Get full token info (scopes, expiry, hub ID) - a single API call:**
```bash
# Returns JSON: token, user, hub_id, scopes[], expires_in
curl "https://api.hubapi.com/oauth/v1/access-tokens/<your-access-token>" \
  > hubspot_token_info.json
```

**Scan it directly:**
```bash
curl "https://api.hubapi.com/oauth/v1/access-tokens/<token>" | \
  jq '{target: "hubspot_integration", json_data: {source_app: "hubspot", oauth: {scopes: .scopes}, credentials: {access_token: .token, expires_in_days: ((.expires_in / 86400) | floor)}}}' | \
  curl -s -X POST http://localhost:8000/scan/analyze -H "Content-Type: application/json" -d @-
```

---

### ServiceNow

**Export OAuth app config via REST API:**
```bash
# Returns JSON: client_id, client_secret, redirect_url, etc.
curl -u <admin-user>:<password> \
  "https://<instance>.service-now.com/api/now/table/oauth_entity?sysparm_query=name=<app-name>&sysparm_fields=client_id,client_secret,redirect_url,type" \
  > servicenow_oauth.json
```

---

### Workday

**Export integration system user config via Workday REST API:**
```bash
# Workday RAAS (Report-as-a-Service) endpoint - export integration configs
curl -u <isu-user>:<password> \
  "https://<tenant>.workday.com/ccx/service/<tenant>/integrations/v1/integrationSystems" \
  > workday_integrations.json
```

---

### Zendesk

**List all OAuth clients:**
```bash
# Returns JSON array: id, name, identifier, redirect_uri, scopes
curl -u <email>/token:<api-token> \
  "https://<subdomain>.zendesk.com/api/v2/oauth/clients.json" \
  > zendesk_oauth_clients.json
```

**List all API tokens:**
```bash
curl -u <email>/token:<api-token> \
  "https://<subdomain>.zendesk.com/api/v2/oauth/tokens.json" \
  > zendesk_tokens.json
```

---

## How to Submit

**The JSON you export from any platform API can be submitted to SaaSShadow directly.** The scanner walks the full JSON tree, so it picks up scopes, tokens, secrets, and credentials at any nesting depth - regardless of the platform's original response format.

**Single integration - scan a file:**
```bash
curl -X POST http://localhost:8000/scan/analyze \
  -H "Content-Type: application/json" \
  -d @my_integration.json
```

**Wrap any API response in the SaaSShadow envelope and scan it:**
```bash
# Generic pattern - works with any platform API output
cat platform_export.json | \
  jq '{target: "my_integration_name", json_data: {source_app: "platform_a", destination_app: "platform_b"} + .}' | \
  curl -s -X POST http://localhost:8000/scan/analyze -H "Content-Type: application/json" -d @-
```

**Get a PDF report:**
```bash
curl -X POST http://localhost:8000/scan/report/pdf \
  -H "Content-Type: application/json" \
  -d @my_integration.json -o report.pdf
```

**Get a JSON report:**
```bash
curl -X POST http://localhost:8000/scan/report/json \
  -H "Content-Type: application/json" \
  -d @my_integration.json
```

---

## Platform-by-Platform Extraction (Detailed)

### Microsoft 365 / Azure AD

**Where to find it:**
1. Go to [Azure Portal → App Registrations](https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade)
2. Select the app registration used by your integration
3. **API Permissions** tab → lists all granted OAuth scopes
4. **Certificates & secrets** tab → shows client secret metadata (not values - record those at creation time)
5. **Token configuration** tab → shows token lifetime policies

**How to extract:**
```bash
# Azure CLI - list app permissions
az ad app show --id <app-id> --query "requiredResourceAccess[].resourceAccess[].id"

# Microsoft Graph API - get OAuth2 permission grants
GET https://graph.microsoft.com/v1.0/oauth2PermissionGrants?$filter=clientId eq '{service-principal-id}'
```

**Example JSON:**
```json
{
  "target": "m365_to_salesforce_sync",
  "json_data": {
    "source_app": "microsoft365",
    "destination_app": "salesforce",
    "oauth": {
      "provider": "azure_ad",
      "scopes": [
        "openid", "profile", "offline_access",
        "Calendars.ReadWrite", "Contacts.ReadWrite",
        "Mail.Send", "User.Read.All",
        "Directory.ReadWrite.All", "Sites.Manage.All"
      ]
    },
    "credentials": {
      "access_token": "<paste JWT here for entropy analysis>",
      "expires_in_days": 365
    },
    "data_types": ["pii", "customer_data"]
  },
  "metadata": { "token_rotation_enabled": false }
}
```

---

### Google Workspace

**Where to find it:**
1. Go to [Google Cloud Console → APIs & Services → Credentials](https://console.cloud.google.com/apis/credentials)
2. Click the OAuth 2.0 Client ID used by the integration
3. **Scopes** are defined in the OAuth consent screen configuration
4. For service accounts: [IAM & Admin → Service Accounts](https://console.cloud.google.com/iam-admin/serviceaccounts) → Keys tab

**How to extract:**
```bash
# gcloud CLI - list service account keys
gcloud iam service-accounts keys list --iam-account=<sa-email>

# Google Admin SDK - list OAuth tokens granted by users
GET https://admin.googleapis.com/admin/directory/v1/users/{userKey}/tokens
```

**Example JSON:**
```json
{
  "target": "google_workspace_to_hubspot",
  "json_data": {
    "source_app": "google_workspace",
    "destination_app": "hubspot",
    "oauth": {
      "provider": "google",
      "scopes": [
        "https://www.googleapis.com/auth/contacts",
        "https://www.googleapis.com/auth/contacts.readonly",
        "https://www.googleapis.com/auth/userinfo.email"
      ]
    },
    "credentials": {
      "access_token": "ya29.a0AfH6SM...",
      "refresh_token": "1//0d4xYz...",
      "expires_in_days": 7
    },
    "data_types": ["pii", "customer_data"]
  },
  "metadata": { "token_rotation_enabled": true }
}
```

---

### Salesforce

**Where to find it:**
1. **Setup → Apps → Connected Apps** → select the integration app
2. **OAuth Policies** section shows permitted scopes
3. **Setup → Security → Session Settings** → token lifetime
4. **Setup → Identity → OAuth and OpenID Connect Settings** for refresh token policy

**How to extract:**
```bash
# Salesforce CLI - list connected apps
sf org list auth

# REST API - query connected app OAuth metadata
GET /services/data/v59.0/sobjects/ConnectedApplication/<id>
```

**Example JSON:**
```json
{
  "target": "salesforce_to_slack_alerts",
  "json_data": {
    "source_app": "salesforce",
    "destination_app": "slack",
    "oauth": {
      "scopes": ["api", "refresh_token", "full"]
    },
    "credentials": {
      "access_token": "00D...",
      "refresh_token": "5Aep...",
      "expires_in_days": 90
    },
    "data_types": ["pii", "customer_data"]
  },
  "metadata": { "token_rotation_enabled": false }
}
```

---

### Slack

**Where to find it:**
1. Go to [api.slack.com/apps](https://api.slack.com/apps) → select your app
2. **OAuth & Permissions** page → lists Bot Token Scopes and User Token Scopes
3. **Install App** section → shows the bot token (`xoxb-...`) and user token (`xoxp-...`)
4. **Event Subscriptions** / **Interactivity** → shows webhook URLs

**How to extract:**
```bash
# Slack API - check current token scopes
curl -H "Authorization: Bearer xoxb-your-token" \
  https://slack.com/api/auth.test

# List all app installations (admin)
curl -H "Authorization: Bearer xoxp-admin-token" \
  https://slack.com/api/admin.apps.approved.list
```

**Example JSON:**
```json
{
  "target": "slack_to_jira_tickets",
  "json_data": {
    "source_app": "slack",
    "destination_app": "jira",
    "oauth": {
      "scopes": [
        "channels:read", "channels:history",
        "chat:write", "reactions:read",
        "users:read", "users:read.email"
      ]
    },
    "credentials": {
      "slack_bot_token": "xoxb-1234567890123-...",
      "expires_in_days": 90
    },
    "data_types": ["customer_data"]
  },
  "metadata": { "token_rotation_enabled": true }
}
```

---

### GitHub

**Where to find it:**
1. **Settings → Developer settings → [GitHub Apps](https://github.com/settings/apps)** or **OAuth Apps**
2. For GitHub Apps: **Permissions & events** tab shows required permissions
3. **Settings → Developer settings → Personal access tokens** → lists PATs and their scopes
4. Organization-level: **Settings → Third-party access → GitHub Apps**

**How to extract:**
```bash
# GitHub CLI - list your token's scopes
gh auth status

# GitHub API - check token permissions
curl -H "Authorization: Bearer ghp_..." \
  https://api.github.com/rate_limit
# Response X-OAuth-Scopes header lists granted scopes

# List organization installations
gh api /orgs/{org}/installations
```

**Example JSON:**
```json
{
  "target": "github_to_slack_notifications",
  "json_data": {
    "source_app": "github",
    "destination_app": "slack",
    "oauth": {
      "scopes": ["repo", "read:org", "admin:repo_hook"]
    },
    "credentials": {
      "github_token": "ghp_a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8"
    },
    "data_types": ["credentials"]
  },
  "metadata": { "token_rotation_enabled": false }
}
```

---

### AWS (IAM / SSO)

**Where to find it:**
1. **IAM Console → Users → Security credentials** → access keys
2. **IAM → Roles → Trust relationships** → shows federated access from other SaaS (Okta, Azure AD)
3. **IAM → Policies** → shows what the integration can access
4. **CloudTrail** → `CreateAccessKey`, `AssumeRole` events show integration usage

**How to extract:**
```bash
# AWS CLI - list access keys for a user
aws iam list-access-keys --user-name integration-service

# List role policies (what the integration can do)
aws iam list-attached-role-policies --role-name SaaSIntegrationRole

# Check key age (rotation hygiene)
aws iam get-access-key-last-used --access-key-id AKIAIOSFODNN7EXAMPLE
```

**Example JSON:**
```json
{
  "target": "aws_to_datadog_monitoring",
  "json_data": {
    "source_app": "aws",
    "destination_app": "datadog",
    "credentials": {
      "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
      "aws_secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
      "datadog_api_key": "a1b2c3d4e5f6..."
    },
    "data_types": ["credentials"]
  },
  "metadata": { "token_rotation_enabled": false }
}
```

---

### Okta

**Where to find it:**
1. **Admin Console → Applications → Applications** → select the app
2. **Sign On** tab → shows SAML/OIDC config and scopes
3. **Admin Console → Security → API → Tokens** → lists API tokens
4. **System Log** → filter for `app.oauth2.as.token.grant` events

**How to extract:**
```bash
# Okta API - list apps and their credentials
curl -H "Authorization: SSWS <api-token>" \
  https://{yourOktaDomain}/api/v1/apps

# List OAuth scopes for an authorization server
curl -H "Authorization: SSWS <api-token>" \
  https://{yourOktaDomain}/api/v1/authorizationServers/{authServerId}/scopes
```

**Example JSON:**
```json
{
  "target": "okta_to_aws_sso",
  "json_data": {
    "source_app": "okta",
    "destination_app": "aws",
    "oauth": {
      "scopes": ["openid", "profile", "email", "groups"]
    },
    "credentials": {
      "access_token": "eyJraWQiOi...",
      "expires_in_days": 1
    }
  },
  "metadata": { "token_rotation_enabled": true }
}
```

---

### Stripe

**Where to find it:**
1. **Stripe Dashboard → Developers → API keys** → publishable and secret keys
2. **Developers → Webhooks** → lists webhook endpoints and their secrets
3. **Connect settings** → shows OAuth scopes for connected accounts

**How to extract:**
```bash
# Stripe CLI - list webhook endpoints
stripe webhook_endpoints list

# Get webhook endpoint details including the signing secret
stripe webhook_endpoints retrieve we_1234567890
```

**Example JSON:**
```json
{
  "target": "stripe_to_netsuite_billing",
  "json_data": {
    "source_app": "stripe",
    "destination_app": "netsuite",
    "credentials": {
      "stripe_secret_key": "sk_live_51ABC...",
      "stripe_webhook_secret": "whsec_a1b2c3d4..."
    },
    "webhook_url": "https://erp.company.com/webhook?secret=whsec_a1b2c3d4...",
    "data_types": ["financial", "pii"]
  },
  "metadata": { "token_rotation_enabled": false }
}
```

---

### Jira / Atlassian Cloud

**Where to find it:**
1. **admin.atlassian.com → Settings → API tokens** → user-generated tokens
2. **Developer console → OAuth 2.0 apps** → shows scopes and client credentials
3. **Jira Settings → System → Webhooks** → lists webhook URLs

**How to extract:**
```bash
# Atlassian API - list OAuth app scopes
curl -H "Authorization: Basic <base64>" \
  https://api.atlassian.com/ex/jira/{cloudId}/rest/api/3/myself

# Check what scopes your app token has
curl -H "Authorization: Bearer <access_token>" \
  https://api.atlassian.com/oauth/token/accessible-resources
```

**Example JSON:**
```json
{
  "target": "jira_to_slack_tickets",
  "json_data": {
    "source_app": "jira",
    "destination_app": "slack",
    "oauth": {
      "scopes": ["read:jira-work", "write:jira-work", "read:jira-user"]
    },
    "credentials": {
      "api_token": "<your-atlassian-api-token>",
      "access_token": "<your-oauth-access-token>",
      "expires_in_days": 90
    },
    "webhook_url": "https://your-app.com/jira-webhook",
    "data_types": ["customer_data"]
  },
  "metadata": { "token_rotation_enabled": true }
}
```

---

### HubSpot

**Where to find it:**
1. **Settings → Integrations → Private Apps** → shows tokens and scopes
2. **Settings → Integrations → Connected Apps** → lists authorized OAuth apps
3. **Settings → Account → API key** (legacy) → shows API key

**How to extract:**
```bash
# HubSpot API - get token info
curl https://api.hubapi.com/oauth/v1/access-tokens/{token}
# Returns: hub_id, user_id, scopes[], expires_in
```

**Example JSON:**
```json
{
  "target": "hubspot_to_salesforce_sync",
  "json_data": {
    "source_app": "hubspot",
    "destination_app": "salesforce",
    "oauth": {
      "scopes": ["crm.objects.contacts.read", "crm.objects.contacts.write", "crm.objects.deals.read"]
    },
    "credentials": {
      "private_app_token": "pat-na1-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
      "refresh_token": "<your-refresh-token>",
      "expires_in_days": 180
    },
    "data_types": ["pii", "customer_data"]
  },
  "metadata": { "token_rotation_enabled": false }
}
```

---

### ServiceNow

**Where to find it:**
1. **System OAuth → Application Registry** → lists all OAuth apps and their scopes
2. **System Web Services → REST Message** → shows outbound integration credentials
3. **System Properties → Certificates** → lists service account credentials

**Example JSON:**
```json
{
  "target": "servicenow_to_pagerduty",
  "json_data": {
    "source_app": "servicenow",
    "destination_app": "pagerduty",
    "oauth": {
      "scopes": ["openid", "profile"]
    },
    "credentials": {
      "api_token": "<your-servicenow-api-token>",
      "pagerduty_api_key": "<your-pagerduty-api-key>",
      "expires_in_days": 60
    },
    "data_types": ["customer_data"]
  },
  "metadata": { "token_rotation_enabled": true }
}
```

---

### Workday

**Where to find it:**
1. **Edit Tenant Setup - Security → API Clients** → lists registered integrations
2. **View API Clients** → shows OAuth scopes per integration user
3. **Integration System Users** → lists service accounts and their permissions

**Example JSON:**
```json
{
  "target": "workday_to_adp_payroll",
  "json_data": {
    "source_app": "workday",
    "destination_app": "adp",
    "oauth": {
      "scopes": ["wd:workers:read", "wd:compensation:read", "wd:payroll:full_access"]
    },
    "credentials": {
      "client_id": "<your-api-client-id>",
      "client_secret": "<your-api-client-secret>",
      "access_token": "<your-access-token>",
      "refresh_token": "<your-refresh-token>",
      "expires_in_days": 180
    },
    "data_types": ["pii", "financial", "health"]
  },
  "metadata": { "token_rotation_enabled": false }
}
```

---

### Zendesk

**Where to find it:**
1. **Admin Center → Apps and integrations → APIs → Zendesk API** → API tokens
2. **Admin Center → Apps and integrations → APIs → OAuth Clients** → registered OAuth apps

**Example JSON:**
```json
{
  "target": "zendesk_to_salesforce_escalation",
  "json_data": {
    "source_app": "zendesk",
    "destination_app": "salesforce",
    "oauth": {
      "scopes": ["tickets:read", "tickets:write", "users:read"]
    },
    "credentials": {
      "api_token": "<your-zendesk-api-token>",
      "access_token": "<your-oauth-access-token>",
      "expires_in_days": 30
    },
    "data_types": ["pii", "customer_data"]
  },
  "metadata": { "token_rotation_enabled": true }
}
```

---

## Batch Scanning (Multiple Integrations)

Wrap multiple integrations into a dataset for batch analysis:

```json
{
  "dataset_name": "q1_2026_integration_audit",
  "items": [
    {
      "integration_id": "m365_to_salesforce",
      "json_data": { "...": "..." },
      "metadata": { "token_rotation_enabled": false }
    },
    {
      "integration_id": "github_to_slack",
      "json_data": { "...": "..." },
      "metadata": { "token_rotation_enabled": true }
    }
  ]
}
```

Submit to the batch endpoint:

```bash
curl -X POST http://localhost:8000/scan/dataset \
  -H "Content-Type: application/json" \
  -d @my_integrations.json
```

The response includes per-integration risk scores plus an aggregate summary with cross-integration token reuse detection.

---

## Automation Tips

### Export from integration platforms (iPaaS)

If you use **Workato**, **Tray.io**, **Zapier**, or **Make (Integromat)**, these platforms typically expose integration metadata via their own APIs:

```bash
# Workato - list connections
curl -H "Authorization: Bearer <workato-token>" \
  https://www.workato.com/api/connections

# Zapier - list zaps (requires partner API access)
# Tray.io - list solutions
curl -H "Authorization: Bearer <tray-token>" \
  https://api.tray.io/core/v1/solutions
```

Transform the response into SaaSShadow's JSON format and submit for analysis.

### Periodic scanning with cron

```bash
# Run every Monday at 9am
0 9 * * 1 curl -X POST http://localhost:8000/scan/dataset \
  -H "Content-Type: application/json" \
  -d @/path/to/integration_inventory.json \
  >> /var/log/saasshadow/weekly_scan.json 2>&1
```

### CI/CD integration

Add to your pipeline to scan integration config changes on every PR:

```yaml
# .github/workflows/saas-audit.yml
- name: Scan SaaS integrations
  run: |
    curl -sf -X POST "$SAASSHADOW_URL/scan/dataset" \
      -H "Content-Type: application/json" \
      -d @integrations.json | jq '.summary'
```

---

## What to Look For

After running a scan, focus on these high-impact signals:

| Signal | What it means | Where to fix |
|---|---|---|
| **OAuth over-permission** | App has admin/wildcard scopes it doesn't need | Reduce scopes in the app registration |
| **Token rotation disabled** | Compromised tokens remain valid indefinitely | Enable rotation in the token policy |
| **Token in URL** | Credentials in query strings appear in logs/proxies | Move to Authorization headers |
| **Long-lived tokens** | Tokens valid >90 days expand the attack window | Reduce TTL, use short-lived + refresh |
| **Cross-platform PII flow** | Personal data moves between SaaS apps | Confirm DPA agreements, minimize data shared |
| **Private key / password exposed** | Raw secret material in integration config | Use vault references or environment variables |
| **AWS/GitHub/Slack token exposed** | Platform-specific credential in plaintext | Rotate immediately, use secrets manager |
