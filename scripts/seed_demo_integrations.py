"""Seed the SaaSShadow demo dashboard with realistic integrations.

Posts a curated set of payloads to ``POST /scan/analyze`` so the basic
dashboard (overview, risk distribution, risk trend, critical findings) and
the scan history light up with believable data for a recorded demo.

Usage
-----

    # Backend must be reachable (defaults to http://127.0.0.1:8000)
    uvicorn app.main:app --reload

    # In another shell:
    python scripts/seed_demo_integrations.py
    python scripts/seed_demo_integrations.py --base-url http://localhost:8000 --customer demo-acme
    python scripts/seed_demo_integrations.py --only salesforce_to_snowflake slack_admin_bot

Each integration is intentionally crafted to trigger one or more of the
SaaSShadow risk dimensions (OAuth over-permission, token misuse, credential
exposure, cross-platform data flow). After it runs, refresh the dashboard
(`/dashboard`) and the scan history (`/scans`) to see the seeded data.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass
class Integration:
    """A single demo payload destined for ``POST /scan/analyze``."""

    key: str
    target: str
    description: str
    json_data: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Demo catalogue
# ---------------------------------------------------------------------------


DEMO_INTEGRATIONS: list[Integration] = [
    Integration(
        key="salesforce_to_snowflake",
        target="salesforce_to_snowflake",
        description=(
            "Marketing ETL pipeline that exports the full Salesforce account, "
            "contact and opportunity history into a Snowflake warehouse via a "
            "service user OAuth grant. Triggers data-flow risk + over-permission."
        ),
        json_data={
            "integration_id": "salesforce_to_snowflake_etl",
            "source_app": "salesforce",
            "destination_app": "snowflake",
            "data_types": ["pii", "customer_data", "financial", "pipeline_revenue"],
            "oauth_config": {
                "client_id": "3MVG9_demo_salesforce_client_id",
                "scopes": [
                    "api",
                    "refresh_token",
                    "full",
                    "web",
                    "chatter_api",
                    "openid",
                    "profile",
                    "email",
                ],
                "redirect_urls": ["https://etl.acme.com/oauth/callback"],
            },
            "tokens": {
                "access_token": "00D5f000001abcd!AQ8AQABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
                "refresh_token": "5Aep861TSESvWeug_demo_refresh_token_value",
                "rotation_days": 365,
            },
            "data_flow": {
                "from_app": "salesforce",
                "to_app": "snowflake",
                "transport": "https",
                "shared_data_types": ["pii", "customer_data", "financial"],
            },
        },
    ),
    Integration(
        key="slack_admin_bot",
        target="slack_datasync_admin_bot",
        description=(
            "Slack bot manifest that grabs `admin`, `chat:write` and "
            "`channels:manage` on the workspace. Classic over-scoped marketplace bot."
        ),
        json_data={
            "integration_id": "slack_datasync_admin_bot",
            "display_information": {
                "name": "DataSync Bot",
                "description": "Syncs CRM contacts into Slack channels",
            },
            "oauth_config": {
                "scopes": {
                    "bot": [
                        "admin",
                        "channels:read",
                        "channels:manage",
                        "chat:write",
                        "files:read",
                        "files:write",
                        "users:read",
                        "users:read.email",
                    ],
                    "user": ["files:read", "search:read", "users.profile:write"],
                },
                "redirect_urls": ["https://app.acme.com/slack/oauth/callback"],
            },
            "source_app": "slack",
            "destination_app": "salesforce",
            "data_types": ["pii", "internal_messages"],
        },
    ),
    Integration(
        key="entra_mail_readwrite",
        target="entra_enterprise_connector",
        description=(
            "Microsoft Entra (Azure AD) enterprise app requesting "
            "`Mail.ReadWrite`, `Directory.ReadWrite.All` and a delegated "
            "`User.Read.All` role. Catastrophic if compromised."
        ),
        json_data={
            "integration_id": "entra_enterprise_connector",
            "source_app": "microsoft_entra",
            "destination_app": "snowflake",
            "data_types": ["pii", "credentials", "directory"],
            "manifest": {
                "appId": "11111111-2222-3333-4444-555555555555",
                "displayName": "Enterprise Data Connector",
                "signInAudience": "AzureADMultipleOrgs",
                "requiredResourceAccess": [
                    {
                        "resourceAppId": "00000003-0000-0000-c000-000000000000",
                        "resourceAccess": [
                            {"id": "e1fe6dd8-ba31-4d61-89e7-88639da4683d", "type": "Scope"},
                            {"id": "e383f46e-2787-4529-855e-0e479a3ffac0", "type": "Scope"},
                            {"id": "863451e7-0667-486c-a5d6-d135439485f0", "type": "Scope"},
                            {"id": "19dbc75e-c2e2-444c-a770-ec596d67c8f0", "type": "Role"},
                        ],
                    }
                ],
                "scopes": [
                    "Mail.ReadWrite",
                    "Mail.Send",
                    "Directory.ReadWrite.All",
                    "User.Read.All",
                    "Files.ReadWrite.All",
                ],
            },
        },
    ),
    Integration(
        key="google_workspace_service_account",
        target="google_workspace_drive_sync",
        description=(
            "Google Workspace service-account JSON checked into a deploy script. "
            "Lights up credential-exposure rules."
        ),
        json_data={
            "integration_id": "google_workspace_drive_sync",
            "source_app": "google_workspace",
            "destination_app": "aws",
            "data_types": ["pii", "documents"],
            "service_account": {
                "type": "service_account",
                "project_id": "acme-prod-12345",
                "private_key_id": "abcdef0123456789abcdef0123456789abcdef01",
                "private_key": (
                    "-----BEGIN PRIVATE KEY-----\nMIIEvAIBADANBgkqhkiG9w0BAQEFAASCBKYwggSiAgEAA"
                    "oIBAQDfake_service_account_private_key_value_for_demo_purposes_only==\n-----END "
                    "PRIVATE KEY-----\n"
                ),
                "client_email": "drive-sync@acme-prod-12345.iam.gserviceaccount.com",
                "client_id": "112233445566778899000",
                "scopes": [
                    "https://www.googleapis.com/auth/drive",
                    "https://www.googleapis.com/auth/admin.directory.user.readonly",
                    "https://www.googleapis.com/auth/gmail.readonly",
                ],
            },
        },
    ),
    Integration(
        key="github_app_admin_org",
        target="github_repo_governance_bot",
        description=(
            "GitHub App with `admin:org`, `repo` (full) and `workflow` "
            "permissions. Common over-grant pattern for internal devops bots."
        ),
        json_data={
            "integration_id": "github_repo_governance_bot",
            "source_app": "github",
            "destination_app": "jira",
            "data_types": ["source_code", "secrets"],
            "app_manifest": {
                "name": "Repo Governance Bot",
                "url": "https://gov.acme.com",
                "default_permissions": {
                    "administration": "write",
                    "contents": "write",
                    "members": "write",
                    "metadata": "read",
                    "organization_administration": "write",
                    "secrets": "write",
                    "workflows": "write",
                },
                "default_events": ["push", "pull_request", "repository", "team"],
                "oauth_scopes": ["repo", "admin:org", "workflow", "write:packages"],
            },
            "tokens": {
                "personal_access_token": "ghp_demoDEMOdemoDEMOdemoDEMOdemoDEMO1234",
                "rotation_days": 720,
            },
        },
    ),
    Integration(
        key="n8n_hubspot_to_sheets",
        target="n8n_hubspot_to_sheets",
        description=(
            "n8n workflow export with hard-coded HubSpot OAuth secret and a "
            "Google Sheets write key embedded in the node. Triggers credential "
            "exposure plus data-flow risk."
        ),
        json_data={
            "integration_id": "n8n_hubspot_to_sheets",
            "source_app": "hubspot",
            "destination_app": "google_workspace",
            "data_types": ["pii", "marketing"],
            "name": "CRM to Spreadsheet Sync",
            "nodes": [
                {
                    "name": "HubSpot Trigger",
                    "type": "n8n-nodes-base.hubspot",
                    "parameters": {
                        "resource": "contact",
                        "operation": "getAll",
                        "authentication": "oAuth2",
                        "client_secret": "hubspot_demo_client_secret_ABCDEFGHIJKLMNOP",
                    },
                },
                {
                    "name": "Google Sheets",
                    "type": "n8n-nodes-base.googleSheets",
                    "parameters": {
                        "operation": "append",
                        "sheetId": "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms",
                        "secret": "gsheet_write_key_demo_123456789012345678",
                    },
                },
                {
                    "name": "Slack Notification",
                    "type": "n8n-nodes-base.slack",
                    "parameters": {"channel": "#crm-updates"},
                },
            ],
        },
    ),
    Integration(
        key="atlassian_connect_act_as_user",
        target="atlassian_jira_exporter",
        description=(
            "Atlassian Connect descriptor requesting `ACT_AS_USER`, `WRITE` and "
            "`PROJECT_ADMIN`. Lets a vendor app impersonate every Jira user."
        ),
        json_data={
            "integration_id": "atlassian_jira_exporter",
            "source_app": "atlassian",
            "destination_app": "aws",
            "data_types": ["pii", "tickets", "customer_data"],
            "manifest": {
                "key": "com.acme.jira-exporter",
                "name": "Project Exporter",
                "baseUrl": "https://addon.acme.com",
                "authentication": {"type": "jwt"},
                "scopes": ["READ", "WRITE", "ACT_AS_USER", "PROJECT_ADMIN"],
                "modules": {
                    "webPanels": [{"key": "export-panel", "url": "/panel"}],
                    "webhooks": [
                        {
                            "event": "jira:issue_created",
                            "url": "/webhook/issue-created",
                        }
                    ],
                },
            },
        },
    ),
    Integration(
        key="zapier_stripe_to_snowflake",
        target="zapier_stripe_to_snowflake",
        description=(
            "Zapier zap exporting Stripe charges into Snowflake with a long-lived "
            "Stripe restricted key. Cross-platform PCI flow."
        ),
        json_data={
            "integration_id": "zapier_stripe_to_snowflake",
            "source_app": "stripe",
            "destination_app": "snowflake",
            "data_types": ["pci", "financial", "pii"],
            "trigger": {
                "app": "stripe",
                "event": "new_charge",
                "auth": {
                    "type": "api_key",
                    "key": "sk_live_demoSTRIPEdemoSTRIPEdemoSTRIPEdemoSTRIPE1234",
                    "rotation_days": 720,
                },
            },
            "actions": [
                {
                    "app": "snowflake",
                    "operation": "insert_row",
                    "table": "fin.stripe_charges",
                    "auth": {
                        "type": "password",
                        "username": "etl_user",
                        "password": "SuperSecret123!",
                    },
                }
            ],
        },
    ),
    Integration(
        key="okta_workflow_offboarding",
        target="okta_offboarding_workflow",
        description=(
            "Okta Workflow that on user offboard deletes the GitHub user, "
            "revokes AWS roles, and posts to Slack. Mostly safe baseline."
        ),
        json_data={
            "integration_id": "okta_offboarding_workflow",
            "source_app": "okta",
            "destination_app": "github",
            "data_types": ["identity", "audit"],
            "oauth_config": {
                "scopes": [
                    "okta.users.read",
                    "okta.groups.read",
                    "okta.events.read",
                ],
                "redirect_urls": ["https://flows.okta.com/oauth/callback"],
            },
            "actions": [
                {"app": "github", "operation": "remove_member", "scopes": ["admin:org"]},
                {"app": "aws", "operation": "revoke_role", "scopes": ["iam:DeleteUser"]},
                {"app": "slack", "operation": "post_message", "scopes": ["chat:write"]},
            ],
            "tokens": {
                "api_token": "00aBcDeF_demo_okta_api_token_value",
                "rotation_days": 30,
            },
        },
    ),
    Integration(
        key="openai_assistant_helpdesk",
        target="openai_helpdesk_copilot",
        description=(
            "OpenAI Assistant hooked into Zendesk tickets, reading customer PII "
            "and sending it to the model. AI / data-flow risk."
        ),
        json_data={
            "integration_id": "openai_helpdesk_copilot",
            "source_app": "zendesk",
            "destination_app": "openai",
            "data_types": ["pii", "customer_data", "support_tickets"],
            "model": "gpt-4o",
            "tools": [
                {"type": "function", "function": {"name": "lookup_ticket"}},
                {"type": "function", "function": {"name": "summarize_thread"}},
                {"type": "retrieval"},
            ],
            "auth": {
                "openai_api_key": "sk-proj-demoOPENAIdemoOPENAIdemoOPENAIdemoOPENAI",
                "zendesk_token": "demoZENDESKtoken1234567890",
            },
            "data_flow": {
                "from_app": "zendesk",
                "to_app": "openai",
                "transport": "https",
                "shared_data_types": ["pii", "customer_data"],
            },
        },
    ),
]


# ---------------------------------------------------------------------------
# Posting
# ---------------------------------------------------------------------------


def _post_json(url: str, payload: dict[str, Any], timeout: float = 30.0) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    with urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else {}


_DIMENSION_LABELS = {
    "oauth_scope_risk": "OAuth",
    "token_misuse": "Token",
    "credential_exposure": "Creds",
    "data_flow_risk": "DataFlow",
}


def _short_risk(result: dict[str, Any]) -> tuple[float, str, list[str]]:
    report = result.get("report") or {}
    score = float(report.get("risk_score") or result.get("combined_score") or 0.0)
    level = str(report.get("risk_level") or "")
    risk_summary = report.get("risk_summary") or result.get("risk_summary") or {}
    dimensions = risk_summary.get("dimension_scores") or report.get("dimension_scores") or {}
    flags: list[str] = []
    for key, label in _DIMENSION_LABELS.items():
        value = dimensions.get(key)
        if isinstance(value, (int, float)) and value > 0:
            flags.append(label)
    return score, level, flags


def seed(
    base_url: str,
    customer_id: str | None,
    only: list[str] | None,
) -> int:
    chosen: list[Integration]
    if only:
        wanted = set(only)
        chosen = [i for i in DEMO_INTEGRATIONS if i.key in wanted]
        missing = wanted - {i.key for i in chosen}
        if missing:
            print(f"Unknown integrations: {', '.join(sorted(missing))}", file=sys.stderr)
            print(
                "Available: " + ", ".join(i.key for i in DEMO_INTEGRATIONS),
                file=sys.stderr,
            )
            return 2
    else:
        chosen = list(DEMO_INTEGRATIONS)

    analyze_url = f"{base_url.rstrip('/')}/scan/analyze"
    print(f"Seeding {len(chosen)} integrations via {analyze_url}")
    print()

    failures: list[tuple[str, str]] = []
    for integration in chosen:
        payload: dict[str, Any] = {
            "target": integration.target,
            "json_data": integration.json_data,
            "metadata": {**integration.metadata, "demo_seed": True},
        }
        if customer_id:
            payload["customer_id"] = customer_id

        started = time.monotonic()
        try:
            result = _post_json(analyze_url, payload)
        except HTTPError as exc:
            failures.append((integration.key, f"HTTP {exc.code}: {exc.reason}"))
            print(f"  [FAIL] {integration.key}: HTTP {exc.code} {exc.reason}")
            continue
        except URLError as exc:
            failures.append((integration.key, str(exc.reason)))
            print(f"  [FAIL] {integration.key}: {exc.reason}")
            continue
        except Exception as exc:  # noqa: BLE001
            failures.append((integration.key, str(exc)))
            print(f"  [FAIL] {integration.key}: {exc}")
            continue

        elapsed = time.monotonic() - started
        score, level, flags = _short_risk(result)
        flag_str = ", ".join(flags) if flags else "none"
        print(
            f"  [OK]   {integration.key:<36} score={score:5.1f}  {level:<8}  "
            f"flags={flag_str:<24}  ({elapsed:.2f}s)"
        )

    print()
    if failures:
        print(f"{len(failures)} integration(s) failed:")
        for key, reason in failures:
            print(f"  - {key}: {reason}")
        return 1
    print("Done. Refresh /dashboard and /scans in the UI to see the seeded data.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Seed the SaaSShadow demo dashboard with realistic integrations.",
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="Backend base URL (default: http://127.0.0.1:8000)",
    )
    parser.add_argument(
        "--customer",
        default=None,
        help="Optional customer_id / tenant id to tag every scan with",
    )
    parser.add_argument(
        "--only",
        nargs="+",
        default=None,
        metavar="KEY",
        help=(
            "Restrict to specific integrations by key. "
            "Available: " + ", ".join(i.key for i in DEMO_INTEGRATIONS)
        ),
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List the available demo integrations and exit",
    )
    args = parser.parse_args()

    if args.list:
        for integration in DEMO_INTEGRATIONS:
            print(f"{integration.key}")
            print(f"    target:      {integration.target}")
            print(f"    description: {integration.description}")
            print()
        return 0

    return seed(
        base_url=args.base_url,
        customer_id=args.customer,
        only=args.only,
    )


if __name__ == "__main__":
    raise SystemExit(main())
