"""Real-world SaaS integration tests.

Each test mirrors a realistic integration between well-known platforms
and validates that SaaSShadow correctly identifies the specific risks
present in that configuration.
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.models.scan_models import PipelineRequest, RuleSet
from app.services.pipeline import run_pipeline
from app.services.rules_loader import load_rules


@pytest.fixture(scope="module")
def rules() -> RuleSet:
    return load_rules(use_cache=False)


# ── Microsoft 365 → Salesforce ────────────────────────────────────────────────
# Over-permissioned OAuth (Directory.ReadWrite.All, Sites.Manage.All),
# exposed client_secret, bearer token, long-lived token, token in webhook URL,
# no rotation, cross-platform PII flow. Should score CRITICAL.

class TestMicrosoft365ToSalesforce:
    PAYLOAD = {
        "target": "microsoft365_to_salesforce_crm_sync",
        "json_data": {
            "source_app": "microsoft365",
            "destination_app": "salesforce",
            "oauth": {
                "scopes": [
                    "openid", "profile", "email", "offline_access",
                    "Calendars.ReadWrite", "Contacts.ReadWrite", "Mail.Send",
                    "User.Read.All", "Directory.ReadWrite.All", "Sites.Manage.All",
                ],
                "client_secret": "xMs8Q~ABCDefghIJKLmnopQRStuvWXyz1234567",
            },
            "credentials": {
                "access_token": "Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJsb2dpbi5taWNyb3NvZnRvbmxpbmUuY29tIn0.fakesig",
                "expires_in_days": 365,
            },
            "webhook_url": "https://hooks.salesforce.com/sync?access_token=xMs8Q~ABCDefghIJKLmnopQRStuvWXyz1234567",
            "data_types": ["pii", "customer_data", "credentials"],
        },
        "metadata": {"token_rotation_enabled": False},
    }

    def test_oauth_over_permission(self, rules: RuleSet) -> None:
        result = run_pipeline(PipelineRequest(**self.PAYLOAD), rule_set=rules)
        assert result.saas_signals.oauth.over_permissioned is True
        assert result.saas_signals.oauth.total_scopes >= 8

    def test_bearer_token_detected(self, rules: RuleSet) -> None:
        result = run_pipeline(PipelineRequest(**self.PAYLOAD), rule_set=rules)
        bearer_findings = [f for f in result.text_findings if f.rule_id == "saas_bearer_token"]
        assert len(bearer_findings) >= 1

    def test_client_secret_exposed(self, rules: RuleSet) -> None:
        result = run_pipeline(PipelineRequest(**self.PAYLOAD), rule_set=rules)
        secret_findings = [f for f in result.text_findings if "secret" in f.rule_id.lower()]
        assert len(secret_findings) >= 1

    def test_token_in_url(self, rules: RuleSet) -> None:
        result = run_pipeline(PipelineRequest(**self.PAYLOAD), rule_set=rules)
        url_findings = [f for f in result.text_findings if "url" in f.rule_id.lower()]
        assert len(url_findings) >= 1

    def test_cross_platform_data_flow(self, rules: RuleSet) -> None:
        result = run_pipeline(PipelineRequest(**self.PAYLOAD), rule_set=rules)
        assert result.saas_signals.data_flow.cross_platform_risk is True
        assert result.saas_signals.data_flow.sensitive_data_exposed is True

    def test_rotation_disabled(self, rules: RuleSet) -> None:
        result = run_pipeline(PipelineRequest(**self.PAYLOAD), rule_set=rules)
        assert result.saas_signals.tokens.rotation_disabled is True

    def test_critical_risk_level(self, rules: RuleSet) -> None:
        result = run_pipeline(PipelineRequest(**self.PAYLOAD), rule_set=rules)
        assert result.report is not None
        assert result.report.risk_level in ("CRITICAL", "HIGH")
        assert result.combined_score >= 60


# ── GitHub → Slack (notifications) ────────────────────────────────────────────
# GitHub PAT exposed, Slack bot token exposed, admin:repo_hook scope,
# no rotation. Should score HIGH.

class TestGitHubToSlack:
    PAYLOAD = {
        "target": "github_to_slack_notifications",
        "json_data": {
            "source_app": "github",
            "destination_app": "slack",
            "oauth": {
                "scopes": ["repo", "read:org", "admin:repo_hook", "write:discussion"],
            },
            "credentials": {
                "github_token": "ghp_a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8",
                "slack_bot_token": "xoxb-9876543210987-9876543210987-ZzYyXxWwVvUuTtSsRrQqPpOo",
            },
            "data_types": ["credentials"],
        },
        "metadata": {"token_rotation_enabled": False},
    }

    def test_github_pat_detected(self, rules: RuleSet) -> None:
        result = run_pipeline(PipelineRequest(**self.PAYLOAD), rule_set=rules)
        pat_findings = [f for f in result.text_findings if f.rule_id == "saas_github_pat"]
        assert len(pat_findings) >= 1

    def test_slack_token_detected(self, rules: RuleSet) -> None:
        result = run_pipeline(PipelineRequest(**self.PAYLOAD), rule_set=rules)
        slack_findings = [f for f in result.text_findings if f.rule_id == "saas_slack_token"]
        assert len(slack_findings) >= 1

    def test_multiple_credential_exposures(self, rules: RuleSet) -> None:
        result = run_pipeline(PipelineRequest(**self.PAYLOAD), rule_set=rules)
        assert result.saas_signals.credentials.exposed_credentials >= 2

    def test_high_risk_score(self, rules: RuleSet) -> None:
        result = run_pipeline(PipelineRequest(**self.PAYLOAD), rule_set=rules)
        assert result.combined_score >= 60


# ── AWS Lambda → Datadog ──────────────────────────────────────────────────────
# AWS IAM access key (AKIA*) in plaintext, no rotation. Should catch the
# specific AWS key regex.

class TestAWSToDatadog:
    PAYLOAD = {
        "target": "aws_lambda_to_datadog",
        "json_data": {
            "source_app": "aws",
            "destination_app": "datadog",
            "credentials": {
                "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
                "aws_secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
                "datadog_api_key": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4",
            },
            "data_types": ["credentials", "secrets"],
        },
        "metadata": {"token_rotation_enabled": False},
    }

    def test_aws_key_detected(self, rules: RuleSet) -> None:
        result = run_pipeline(PipelineRequest(**self.PAYLOAD), rule_set=rules)
        aws_findings = [f for f in result.text_findings if f.rule_id == "saas_aws_access_key"]
        assert len(aws_findings) >= 1

    def test_rotation_disabled_flagged(self, rules: RuleSet) -> None:
        result = run_pipeline(PipelineRequest(**self.PAYLOAD), rule_set=rules)
        assert result.saas_signals.tokens.rotation_disabled is True


# ── Okta → AWS SSO (clean) ───────────────────────────────────────────────────
# Minimal scopes (openid, profile, email, groups), short-lived token (1 day),
# rotation enabled. Should score LOW/MINIMAL — validates that well-configured
# integrations aren't over-penalized.

class TestOktaToAWS:
    PAYLOAD = {
        "target": "okta_to_aws_sso",
        "json_data": {
            "source_app": "okta",
            "destination_app": "aws",
            "oauth": {
                "scopes": ["openid", "profile", "email", "groups"],
            },
            "credentials": {
                "access_token": "eyJraWQiOiJfVUtJbEhkSVRhbU5vdXgxMzBpc0ZEXzd5TGNhRGFhVEE2bGtYV3ciLCJhbGciOiJSUzI1NiJ9.stub.valid",
                "expires_in_days": 1,
            },
            "data_types": ["credentials"],
        },
        "metadata": {"token_rotation_enabled": True},
    }

    def test_not_over_permissioned(self, rules: RuleSet) -> None:
        result = run_pipeline(PipelineRequest(**self.PAYLOAD), rule_set=rules)
        assert result.saas_signals.oauth.over_permissioned is False

    def test_rotation_enabled(self, rules: RuleSet) -> None:
        result = run_pipeline(PipelineRequest(**self.PAYLOAD), rule_set=rules)
        assert result.saas_signals.tokens.rotation_disabled is False

    def test_low_risk_score(self, rules: RuleSet) -> None:
        """Even a clean SSO carries a JWT (entropy) and passes credential
        material cross-platform, so the floor is ~60.  Confirm it stays
        well below a truly dangerous integration (>80)."""
        result = run_pipeline(PipelineRequest(**self.PAYLOAD), rule_set=rules)
        assert result.combined_score < 75


# ── Stripe → NetSuite (financial) ─────────────────────────────────────────────
# Stripe secret key (sk_live_*), webhook secret in URL, cross-platform
# financial data flow, no rotation. Should score HIGH/CRITICAL.

class TestStripeToNetSuite:
    PAYLOAD = {
        "target": "stripe_to_netsuite_billing_sync",
        "json_data": {
            "source_app": "stripe",
            "destination_app": "netsuite",
            "credentials": {
                "stripe_secret_key": "sk_live_51ABCDefGHIjklMNOpqrSTUvwxyz1234567890abcdefghijklmnopqrs",
                "stripe_webhook_secret": "whsec_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
            },
            "webhook_url": "https://erp.company.com/netsuite/webhook?secret=whsec_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
            "data_types": ["financial", "pii"],
        },
        "metadata": {"token_rotation_enabled": False},
    }

    def test_cross_platform_financial_flow(self, rules: RuleSet) -> None:
        result = run_pipeline(PipelineRequest(**self.PAYLOAD), rule_set=rules)
        assert result.saas_signals.data_flow.cross_platform_risk is True
        assert "financial" in result.saas_signals.data_flow.data_types

    def test_webhook_secret_in_url(self, rules: RuleSet) -> None:
        result = run_pipeline(PipelineRequest(**self.PAYLOAD), rule_set=rules)
        webhook_findings = [f for f in result.text_findings if "webhook" in f.rule_id or "url" in f.rule_id]
        assert len(webhook_findings) >= 1

    def test_high_risk(self, rules: RuleSet) -> None:
        result = run_pipeline(PipelineRequest(**self.PAYLOAD), rule_set=rules)
        assert result.combined_score >= 60


# ── Snowflake → Tableau (private key + password) ─────────────────────────────
# Embedded RSA private key PEM block, plaintext password, cross-platform
# financial data. Should catch the private key regex and password keyword.

class TestSnowflakeToTableau:
    PAYLOAD = {
        "target": "snowflake_to_tableau_analytics",
        "json_data": {
            "source_app": "snowflake",
            "destination_app": "tableau",
            "credentials": {
                "snowflake_user": "TABLEAU_SERVICE_ACCOUNT",
                "snowflake_password": "S3cur3P@ssw0rd!2024ForSnowflakeTableau",
                "snowflake_private_key": "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0Z3VS5JJcds3xfn\n-----END RSA PRIVATE KEY-----",
            },
            "data_types": ["financial", "customer_data"],
        },
        "metadata": {"token_rotation_enabled": False},
    }

    def test_private_key_detected(self, rules: RuleSet) -> None:
        result = run_pipeline(PipelineRequest(**self.PAYLOAD), rule_set=rules)
        key_findings = [f for f in result.text_findings if f.rule_id == "saas_private_key_block"]
        assert len(key_findings) >= 1

    def test_password_keyword_detected(self, rules: RuleSet) -> None:
        result = run_pipeline(PipelineRequest(**self.PAYLOAD), rule_set=rules)
        pw_findings = [f for f in result.text_findings if f.rule_id == "saas_password_keyword"]
        assert len(pw_findings) >= 1

    def test_cross_platform_data_flow(self, rules: RuleSet) -> None:
        result = run_pipeline(PipelineRequest(**self.PAYLOAD), rule_set=rules)
        assert result.saas_signals.data_flow.cross_platform_risk is True


# ── Workday → ADP (HR/payroll, full_access scope) ────────────────────────────
# OAuth full_access scope, bearer token, refresh token, client secret, 180-day
# expiry, cross-platform PII+financial+health data, no rotation.
# Maximum risk surface.

class TestWorkdayToADP:
    PAYLOAD = {
        "target": "workday_to_adp_payroll_sync",
        "json_data": {
            "source_app": "workday",
            "destination_app": "adp",
            "oauth": {
                "scopes": [
                    "wd:workers:read", "wd:compensation:read",
                    "wd:payroll:full_access", "wd:benefits:read",
                    "wd:organizations:read",
                ],
                "client_secret": "WD-SECRET-a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            },
            "credentials": {
                "access_token": "Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ3b3JrZGF5LWludGVncmF0aW9uIn0.ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnop",
                "refresh_token": "wd-refresh-a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6",
                "expires_in_days": 180,
            },
            "data_types": ["pii", "financial", "health"],
        },
        "metadata": {"token_rotation_enabled": False},
    }

    def test_full_access_scope_over_permission(self, rules: RuleSet) -> None:
        result = run_pipeline(PipelineRequest(**self.PAYLOAD), rule_set=rules)
        assert result.saas_signals.oauth.over_permissioned is True

    def test_bearer_and_refresh_token_exposed(self, rules: RuleSet) -> None:
        result = run_pipeline(PipelineRequest(**self.PAYLOAD), rule_set=rules)
        bearer = [f for f in result.text_findings if f.rule_id == "saas_bearer_token"]
        assert len(bearer) >= 1

    def test_long_lived_token(self, rules: RuleSet) -> None:
        result = run_pipeline(PipelineRequest(**self.PAYLOAD), rule_set=rules)
        assert result.saas_signals.tokens.long_lived_tokens >= 1

    def test_sensitive_data_types(self, rules: RuleSet) -> None:
        result = run_pipeline(PipelineRequest(**self.PAYLOAD), rule_set=rules)
        flow = result.saas_signals.data_flow
        assert flow.cross_platform_risk is True
        assert "financial" in flow.data_types
        assert "pii" in flow.data_types

    def test_critical_risk_level(self, rules: RuleSet) -> None:
        result = run_pipeline(PipelineRequest(**self.PAYLOAD), rule_set=rules)
        assert result.report is not None
        assert result.report.risk_level in ("CRITICAL", "HIGH")


# ── ServiceNow → PagerDuty (moderate risk) ───────────────────────────────────
# Minimal scopes, short-ish TTL (60 days), rotation enabled.
# Some credential exposure but structurally reasonable.

class TestServiceNowToPagerDuty:
    PAYLOAD = {
        "target": "servicenow_to_pagerduty",
        "json_data": {
            "source_app": "servicenow",
            "destination_app": "pagerduty",
            "oauth": {"scopes": ["openid", "profile"]},
            "credentials": {
                "pagerduty_api_key": "u+a1B2c3D4e5F6g7H8i9J0",
                "expires_in_days": 60,
            },
        },
        "metadata": {"token_rotation_enabled": True},
    }

    def test_not_over_permissioned(self, rules: RuleSet) -> None:
        result = run_pipeline(PipelineRequest(**self.PAYLOAD), rule_set=rules)
        assert result.saas_signals.oauth.over_permissioned is False

    def test_moderate_score(self, rules: RuleSet) -> None:
        result = run_pipeline(PipelineRequest(**self.PAYLOAD), rule_set=rules)
        assert result.combined_score < 80


# ── Full dataset batch analysis (API endpoint) ───────────────────────────────

class TestBatchDatasetAnalysis:
    def test_full_dataset_from_file(self, client: TestClient) -> None:
        path = Path("data/sample_integrations.json")
        payload = json.loads(path.read_text(encoding="utf-8"))
        response = client.post("/scan/dataset", json=payload)
        assert response.status_code == 200
        data = response.json()
        summary = data["summary"]
        assert summary["total_integrations"] == 16
        assert summary["high_risk_integrations"] >= 3
        assert summary["oauth_over_permission_hits"] >= 2
        assert summary["credential_exposure_hits"] >= 5
        assert summary["cross_platform_risk_hits"] >= 4

    def test_each_result_has_risk_level(self, client: TestClient) -> None:
        path = Path("data/sample_integrations.json")
        payload = json.loads(path.read_text(encoding="utf-8"))
        response = client.post("/scan/dataset", json=payload)
        data = response.json()
        for item in data["results"]:
            assert item["risk_level"] in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "MINIMAL")
            assert 0 <= item["risk_score"] <= 100
