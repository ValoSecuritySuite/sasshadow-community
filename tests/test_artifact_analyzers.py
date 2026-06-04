"""Tests for artifact-family analyzers — Entra, ARM, Slack, Atlassian, workflows."""


from app.services.entra_manifest_parser import analyze_entra_manifest
from app.services.arm_template_analyzer import analyze_arm_template
from app.services.workflow_graph_analyzer import analyze_workflow
from app.services.oauth_parser import analyze_scopes, extract_scopes, clear_policy_cache


# ── Entra manifest ────────────────────────────────────────────────────────────


class TestEntraManifestParser:
    def test_detects_entra_manifest(self) -> None:
        payload = {
            "appId": "11111111-2222-3333-4444-555555555555",
            "requiredResourceAccess": [
                {
                    "resourceAppId": "00000003-0000-0000-c000-000000000000",
                    "resourceAccess": [
                        {"id": "e1fe6dd8-ba31-4d61-89e7-88639da4683d", "type": "Scope"},
                    ],
                }
            ],
        }
        result = analyze_entra_manifest(payload)
        assert result is not None
        assert result.total_scopes == 1
        assert "User.Read" in result.scopes

    def test_maps_high_risk_permissions(self) -> None:
        payload = {
            "requiredResourceAccess": [
                {
                    "resourceAppId": "00000003-0000-0000-c000-000000000000",
                    "resourceAccess": [
                        {"id": "e2a3a72e-5f79-4c64-b1b1-878b674786c9", "type": "Scope"},
                        {"id": "204e0828-b5ca-4571-a349-6743c2258ba2", "type": "Scope"},
                        {"id": "e383f46e-2787-4529-855e-0e479a3ffac0", "type": "Scope"},
                    ],
                }
            ],
        }
        result = analyze_entra_manifest(payload)
        assert result is not None
        assert result.over_permissioned is True
        assert result.scope_risk_score > 0
        assert len(result.high_risk_scopes) >= 2

    def test_app_role_permissions_flagged(self) -> None:
        payload = {
            "requiredResourceAccess": [
                {
                    "resourceAppId": "00000003-0000-0000-c000-000000000000",
                    "resourceAccess": [
                        {"id": "19dbc75e-c2e2-444c-a770-ec596d67c8f0", "type": "Role"},
                    ],
                }
            ],
        }
        result = analyze_entra_manifest(payload)
        assert result is not None
        assert len(result.high_risk_scopes) >= 1
        assert any("App" in s.scope for s in result.high_risk_scopes)

    def test_unknown_guid_handled(self) -> None:
        payload = {
            "requiredResourceAccess": [
                {
                    "resourceAppId": "00000003-0000-0000-c000-000000000000",
                    "resourceAccess": [
                        {"id": "ffffffff-ffff-ffff-ffff-ffffffffffff", "type": "Scope"},
                    ],
                }
            ],
        }
        result = analyze_entra_manifest(payload)
        assert result is not None
        assert result.total_scopes == 1
        assert "unknown:" in result.scopes[0]

    def test_non_entra_returns_none(self) -> None:
        payload = {"oauth": {"scopes": ["read"]}}
        assert analyze_entra_manifest(payload) is None

    def test_safe_scopes_not_high_risk(self) -> None:
        payload = {
            "requiredResourceAccess": [
                {
                    "resourceAppId": "00000003-0000-0000-c000-000000000000",
                    "resourceAccess": [
                        {"id": "e1fe6dd8-ba31-4d61-89e7-88639da4683d", "type": "Scope"},
                        {"id": "37f7f235-527c-4136-accd-4a02d197296e", "type": "Scope"},
                        {"id": "570282fd-fa5c-430d-a7fd-fc8dc98a9dca", "type": "Scope"},
                    ],
                }
            ],
        }
        result = analyze_entra_manifest(payload)
        assert result is not None
        assert len(result.high_risk_scopes) == 0
        assert len(result.safe_scopes) == 3


# ── ARM template analyzer ────────────────────────────────────────────────────


class TestARMTemplateAnalyzer:
    def test_detects_arm_template(self) -> None:
        payload = {
            "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#",
            "parameters": {
                "appName": {"type": "string", "defaultValue": "myapp"}
            },
            "resources": [],
        }
        result = analyze_arm_template("", payload)
        assert result.is_arm_template is True

    def test_flags_insecure_string_params(self) -> None:
        payload = {
            "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#",
            "parameters": {
                "sqlPassword": {"type": "string", "defaultValue": "P@ssw0rd123!"},
                "apiSecretKey": {"type": "string"},
                "appName": {"type": "string"},
            },
            "resources": [],
        }
        result = analyze_arm_template("", payload)
        assert len(result.insecure_params) == 2
        assert result.arm_risk_score > 0

    def test_detects_connections_object(self) -> None:
        payload = {
            "parameters": {
                "$connections": {
                    "value": {
                        "office365": {"connectionId": "/subscriptions/xxx/connections/o365"},
                        "sql": {"connectionId": "/subscriptions/xxx/connections/sql"},
                    }
                }
            },
            "resources": [],
        }
        result = analyze_arm_template("", payload)
        assert len(result.connections_found) == 2
        assert "office365" in result.connections_found

    def test_detects_inline_basic_auth(self) -> None:
        payload = {
            "actions": {
                "CallApi": {
                    "name": "CallApi",
                    "type": "Http",
                    "inputs": {
                        "authentication": {
                            "type": "basic",
                            "password": "my-secret-password-123"
                        }
                    },
                }
            }
        }
        result = analyze_arm_template("", payload)
        assert len(result.inline_credentials) >= 1

    def test_detects_connection_strings_in_content(self) -> None:
        content = 'Server=myserver.database.windows.net;Database=mydb;User Id=admin;Password=S3cret!'
        result = analyze_arm_template(content, {})
        assert any("SQL connection string" in f for f in result.findings)

    def test_clean_template_no_findings(self) -> None:
        payload = {
            "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#",
            "parameters": {
                "password": {"type": "secureString"},
                "location": {"type": "string"},
            },
            "resources": [],
        }
        result = analyze_arm_template("", payload)
        assert len(result.insecure_params) == 0
        assert result.arm_risk_score == 0.0

    def test_secret_in_default_value(self) -> None:
        payload = {
            "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#",
            "parameters": {
                "storageKey": {
                    "type": "string",
                    "defaultValue": "abc123DEF456ghi789JKL012mno345PQR678stu901"
                },
            },
            "resources": [],
        }
        result = analyze_arm_template("", payload)
        assert len(result.connection_strings_in_defaults) >= 1


# ── Workflow graph analyzer ───────────────────────────────────────────────────


class TestWorkflowGraphAnalyzer:
    def test_detect_n8n_workflow(self) -> None:
        payload = {
            "nodes": [
                {"name": "Start", "type": "n8n-nodes-base.hubspot", "parameters": {}, "credentials": {"hubspotApi": {"id": "1"}}},
                {"name": "Sheets", "type": "n8n-nodes-base.googleSheets", "parameters": {}, "credentials": {}},
            ]
        }
        result = analyze_workflow("", payload)
        assert result.platform == "n8n"
        assert result.node_count == 2
        assert len(result.saas_connectors) == 2
        assert "hubspot" in result.inferred_services
        assert "google_sheets" in result.inferred_services

    def test_detect_nodered_flow(self) -> None:
        payload = [
            {"id": "1", "type": "slack in", "name": "Slack", "wires": [["2"]]},
            {"id": "2", "type": "http request", "name": "API Call", "wires": []},
        ]
        result = analyze_workflow("", payload)
        assert result.platform == "node-red"
        assert result.node_count == 2

    def test_detect_logic_apps(self) -> None:
        payload = {
            "definition": {
                "triggers": {"on_email": {"type": "ApiConnection", "inputs": {}}},
                "actions": {
                    "notify": {
                        "type": "ApiConnection",
                        "inputs": {
                            "host": {
                                "connection": {"name": "slack"}
                            }
                        },
                    }
                },
            }
        }
        result = analyze_workflow("", payload)
        assert result.platform == "logic-apps"
        assert result.node_count == 2

    def test_detect_step_functions(self) -> None:
        payload = {
            "StartAt": "Extract",
            "States": {
                "Extract": {
                    "Type": "Task",
                    "Resource": "arn:aws:lambda:us-east-1:123:function:extract",
                    "Parameters": {},
                    "Next": "Load",
                },
                "Load": {
                    "Type": "Task",
                    "Resource": "arn:aws:states:::redshift-data:executeStatement",
                    "Parameters": {},
                    "End": True,
                },
            },
        }
        result = analyze_workflow("", payload)
        assert result.platform == "step-functions"
        assert result.node_count == 2
        assert "lambda" in result.inferred_services

    def test_n8n_inline_credential_flagged(self) -> None:
        payload = {
            "nodes": [
                {
                    "name": "API Call",
                    "type": "n8n-nodes-base.httpRequest",
                    "parameters": {
                        "url": "https://api.example.com",
                        "authentication": "bearer_token_here_1234567890"
                    },
                    "credentials": {},
                },
            ]
        }
        result = analyze_workflow("", payload)
        assert len(result.findings) >= 1
        assert any(f.category == "inline_credential" for f in result.findings)

    def test_step_functions_inline_api_key(self) -> None:
        payload = {
            "StartAt": "Call",
            "States": {
                "Call": {
                    "Type": "Task",
                    "Resource": "arn:aws:lambda:us-east-1:123:function:call",
                    "Parameters": {
                        "api_key": "sk_live_ABCDEFGHIJKLMNOPQRSTUVWXYZ1234"
                    },
                    "End": True,
                },
            },
        }
        result = analyze_workflow("", payload)
        assert len(result.findings) >= 1
        assert result.workflow_risk_score > 0

    def test_unknown_payload_returns_empty(self) -> None:
        result = analyze_workflow("", {"random": "data"})
        assert result.platform is None
        assert result.node_count == 0

    def test_webhook_secret_in_url_detected(self) -> None:
        payload = {
            "nodes": [
                {
                    "name": "Webhook",
                    "type": "n8n-nodes-base.webhook",
                    "parameters": {
                        "url": "https://hooks.example.com/webhook?secret=my_webhook_secret_value_123"
                    },
                    "credentials": {},
                },
            ]
        }
        result = analyze_workflow("", payload)
        assert len(result.webhook_urls) >= 1


# ── Slack manifest scope extraction ───────────────────────────────────────────


class TestSlackManifestScopes:
    def setup_method(self):
        clear_policy_cache()

    def test_extract_bot_and_user_scopes(self) -> None:
        payload = {
            "oauth_config": {
                "scopes": {
                    "bot": ["channels:read", "chat:write", "admin"],
                    "user": ["files:read"]
                }
            }
        }
        scopes = extract_scopes(payload)
        assert "channels:read" in scopes
        assert "chat:write" in scopes
        assert "admin" in scopes
        assert "files:read" in scopes

    def test_analyze_slack_manifest_over_permission(self) -> None:
        payload = {
            "oauth_config": {
                "scopes": {
                    "bot": ["channels:manage", "files:write", "users:write", "admin"],
                    "user": ["users.profile:write"]
                }
            }
        }
        result = analyze_scopes(payload)
        assert result.over_permissioned is True
        assert result.scope_risk_score > 0
        assert len(result.high_risk_scopes) >= 2

    def test_slack_safe_scopes_only(self) -> None:
        payload = {
            "oauth_config": {
                "scopes": {
                    "bot": ["channels:read", "users:read", "team:read"]
                }
            }
        }
        result = analyze_scopes(payload)
        assert result.over_permissioned is False


# ── Atlassian Connect scope extraction ────────────────────────────────────────


class TestAtlassianConnectScopes:
    def setup_method(self):
        clear_policy_cache()

    def test_extract_atlassian_scopes(self) -> None:
        payload = {
            "key": "com.example.addon",
            "scopes": ["READ", "WRITE", "ACT_AS_USER"],
        }
        scopes = extract_scopes(payload)
        assert "read" in scopes
        assert "write" in scopes
        assert "act_as_user" in scopes

    def test_analyze_atlassian_high_risk(self) -> None:
        payload = {
            "scopes": ["READ", "WRITE", "ACT_AS_USER", "PROJECT_ADMIN"],
        }
        result = analyze_scopes(payload)
        assert result.over_permissioned is True
        assert any("act_as_user" in s.scope for s in result.high_risk_scopes)
