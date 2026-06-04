"""Tests for the credential exposure scanner (app/analyzers/credential_exposure)."""


from app.analyzers.credential_exposure import (
    scan_credentials,
)
from app.services.pipeline import run_pipeline_raw


class TestCredentialExposureRegex:
    """Regex detectors: AWS, OAuth, API keys, private keys."""

    def test_aws_access_key_detected(self) -> None:
        content = '{"AWS_ACCESS_KEY_ID": "AKIAIOSFODNN7EXAMPLE", "region": "us-east-1"}'
        result = scan_credentials(content, location="config.json")
        assert len(result.findings) >= 1
        aws = [f for f in result.findings if "AWS" in f.credential_type]
        assert len(aws) == 1
        assert aws[0].risk == "CRITICAL"
        assert aws[0].location != ""
        assert aws[0].detection_method == "regex"

    def test_bearer_token_detected(self) -> None:
        content = 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U'
        result = scan_credentials(content, location="headers.txt")
        assert len(result.findings) >= 1
        bearer = [f for f in result.findings if "Bearer" in f.credential_type]
        assert len(bearer) == 1
        assert bearer[0].severity == 5

    def test_client_secret_detected(self) -> None:
        content = 'client_secret=GOCSPX-abcdefghijklmnopqrstuvwxyz123456'
        result = scan_credentials(content)
        assert any("Client Secret" in f.credential_type for f in result.findings)

    def test_api_key_detected(self) -> None:
        content = '{"api_key": "sk_live_ABCDEFGHIJKLMNOPQRSTUVWXYZ12345678"}'
        result = scan_credentials(content)
        # Could be API Key or Stripe key pattern
        assert len(result.findings) >= 1
        assert any(f.credential_type in ("API Key", "Stripe API Key") for f in result.findings)

    def test_github_pat_detected(self) -> None:
        content = 'token: ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
        result = scan_credentials(content, location="config.yaml")
        assert len(result.findings) >= 1
        assert any("GitHub" in f.credential_type for f in result.findings)

    def test_slack_token_detected(self) -> None:
        content = 'xoxb-1234567890123-1234567890123-abcdefghijklmnopqrstuvwx'
        result = scan_credentials(content)
        assert any("Slack" in f.credential_type for f in result.findings)

    def test_private_key_pem_detected(self) -> None:
        content = """
        -----BEGIN RSA PRIVATE KEY-----
        MIIEowIBAAKCAQEA0Z3VS5JJcds3xfnJgTdVUr4UfQ
        -----END RSA PRIVATE KEY-----
        """
        result = scan_credentials(content, location="key.pem")
        assert any("Private Key" in f.credential_type for f in result.findings)

    def test_token_in_url_detected(self) -> None:
        content = "https://api.example.com/data?access_token=abc123def456ghi789"
        result = scan_credentials(content)
        assert any("Token in URL" in f.credential_type for f in result.findings)


class TestCredentialExposureEntropy:
    """Entropy-based detection for unknown secrets."""

    def test_high_entropy_quoted_string_flagged(self) -> None:
        content = '"superSecretValueK9$xL2mN8pQ4rT6vW1zA3bC5dE7fG9hJ0"'
        result = scan_credentials(content)
        assert any(f.detection_method == "entropy" for f in result.findings)
        assert any("High-Entropy" in f.credential_type for f in result.findings)

    def test_low_entropy_not_flagged(self) -> None:
        content = '"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"'
        result = scan_credentials(content)
        entropy_findings = [f for f in result.findings if f.detection_method == "entropy"]
        assert len(entropy_findings) == 0

    def test_uuid_not_flagged_as_entropy(self) -> None:
        content = '"a1b2c3d4-e5f6-7890-abcd-ef1234567890"'
        result = scan_credentials(content)
        entropy_findings = [f for f in result.findings if f.detection_method == "entropy"]
        assert len(entropy_findings) == 0


class TestCredentialExposureLocationAndRisk:
    """Example finding: Type, Risk, Location."""

    def test_finding_has_type_risk_location(self) -> None:
        content = "AKIAIOSFODNN7EXAMPLE"
        result = scan_credentials(content, location="config.yaml")
        assert len(result.findings) >= 1
        f = result.findings[0]
        assert f.credential_type
        assert f.risk in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "MINIMAL")
        assert "config.yaml" in f.location or "line" in f.location

    def test_risk_score_computed(self) -> None:
        content = "AKIAIOSFODNN7EXAMPLE\nBearer eyJhbGciOiJIUzI1NiJ9.xxx.yyy"
        result = scan_credentials(content)
        assert result.credential_risk_score > 0
        assert result.credential_risk_score <= 100


class TestCredentialExposureIntegrationMapping:
    """Map findings to affected SaaS integrations."""

    def test_integration_context_attached(self) -> None:
        content = "api_key=sk_live_abcdefghijklmnop1234567890"
        ctx = {"target": "stripe_to_quickbooks", "source_app": "stripe", "destination_app": "quickbooks"}
        result = scan_credentials(content, location="env.json", integration_context=ctx)
        assert len(result.findings) >= 1
        assert result.findings[0].integration_context == ctx

    def test_findings_by_integration_populated(self) -> None:
        content = "AKIAIOSFODNN7EXAMPLE"
        ctx = {"target": "my_integration"}
        result = scan_credentials(content, integration_context=ctx)
        assert "my_integration" in result.findings_by_integration
        assert result.findings_by_integration["my_integration"] == [0]


class TestCredentialExposureToTextFindings:
    """Conversion to TextFinding for pipeline merge."""

    def test_to_text_findings_has_credential_prefix(self) -> None:
        content = "AKIAIOSFODNN7EXAMPLE"
        result = scan_credentials(content)
        text_findings = result.to_text_findings()
        assert len(text_findings) == len(result.findings)
        assert all(tf.rule_id.startswith("credential_") for tf in text_findings)


class TestCredentialExposurePipelineIntegration:
    """Scanner wired into pipeline and report."""

    def test_pipeline_populates_credential_scan_findings(self) -> None:
        json_data = {
            "source_app": "salesforce",
            "destination_app": "slack",
            "credentials": {
                "access_token": "Bearer eyJhbGciOiJIUzI1NiJ9.very-long-jwt-token-value-here",
                "client_secret": "s3cr3tK3yV4lu3",
            },
        }
        result = run_pipeline_raw(json_data, target="test_integration")
        creds = result.saas_signals.credentials
        assert creds.exposed_credentials >= 1
        assert hasattr(creds, "credential_scan_findings")
        assert isinstance(creds.credential_scan_findings, list)
        if creds.credential_scan_findings:
            f = creds.credential_scan_findings[0]
            assert f.credential_type
            assert f.risk in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "MINIMAL")

    def test_report_includes_credential_scan_findings(self) -> None:
        result = run_pipeline_raw(
            "api_key=sk_live_ABCDEFGHIJKLMNOPQRSTUVWXYZ1234",
            target="test",
        )
        assert result.report is not None
        assert result.report.credential_exposure is not None
        assert hasattr(result.report.credential_exposure, "credential_scan_findings")
