"""Tests for SaaS-specific analysis services — OAuth, token, credential, risk."""


from app.services.oauth_parser import analyze_scopes, extract_scopes, clear_policy_cache
from app.services.token_analyzer import analyze_tokens, shannon_entropy
from app.services.credential_detector import detect_credential_exposure, count_credential_exposure_findings
from app.services.risk_engine import analyze_data_flow, compute_composite_score, risk_level_from_score
from app.models.scan_models import (
    OAuthAnalysis,
    TokenAnalysis,
    CredentialExposure,
    DataFlowRisk,
    SaaSSignalSummary,
    TextFinding,
    TextScanResult,
)


class TestOAuthParser:
    def setup_method(self):
        clear_policy_cache()

    def test_extract_scopes_from_list(self) -> None:
        payload = {"oauth": {"scopes": ["read", "write", "admin"]}}
        scopes = extract_scopes(payload)
        assert "read" in scopes
        assert "write" in scopes
        assert "admin" in scopes

    def test_extract_scopes_from_string(self) -> None:
        payload = {"oauth_scopes": "contacts.read contacts.write notes.write"}
        scopes = extract_scopes(payload)
        assert len(scopes) == 3

    def test_analyze_detects_over_permission(self) -> None:
        payload = {
            "oauth": {
                "scopes": ["files.readwrite.all", "users.readwrite.all", "offline_access"]
            }
        }
        result = analyze_scopes(payload)
        assert isinstance(result, OAuthAnalysis)
        assert result.over_permissioned is True
        assert result.scope_risk_score > 0

    def test_analyze_safe_scopes_not_flagged(self) -> None:
        payload = {"oauth": {"scopes": ["openid", "profile", "email"]}}
        result = analyze_scopes(payload)
        assert result.over_permissioned is False
        assert len(result.high_risk_scopes) == 0

    def test_analyze_wildcard_scopes(self) -> None:
        payload = {"oauth": {"scope": "drive.* files.readwrite.all"}}
        result = analyze_scopes(payload)
        assert len(result.wildcard_scopes) >= 1

    def test_empty_payload_returns_empty(self) -> None:
        result = analyze_scopes({})
        assert result.total_scopes == 0


class TestTokenAnalyzer:
    def test_detect_token_without_expiry(self) -> None:
        payload = {"credentials": {"access_token": "some-long-token-value-here-1234567890"}}
        result = analyze_tokens("", payload, {})
        assert "token_without_expiry" in result.misuse_patterns

    def test_detect_long_lived_token(self) -> None:
        payload = {
            "credentials": {"access_token": "some-long-token-value-1234567890"},
            "expires_in_days": 180,
        }
        result = analyze_tokens("", payload, {})
        assert "long_lived_token" in result.misuse_patterns

    def test_detect_token_in_url(self) -> None:
        content = "https://api.example.com/data?access_token=abc123"
        result = analyze_tokens(content, {}, {})
        assert "token_in_url_query" in result.misuse_patterns

    def test_detect_rotation_disabled(self) -> None:
        result = analyze_tokens("", {}, {"token_rotation_enabled": False})
        assert "rotation_disabled" in result.misuse_patterns
        assert result.rotation_disabled is True

    def test_detect_shared_tokens(self) -> None:
        result = analyze_tokens("", {}, {"token_shared_across_integrations": True})
        assert "token_reuse_across_integrations" in result.misuse_patterns

    def test_shannon_entropy_high_for_random(self) -> None:
        assert shannon_entropy("aB3$kL9!mN") > 3.0

    def test_shannon_entropy_low_for_repeated(self) -> None:
        assert shannon_entropy("aaaaaaaaaa") == 0.0

    def test_clean_payload_no_misuse(self) -> None:
        payload = {"credentials": {"access_token": "short"}, "expires_in_days": 7}
        result = analyze_tokens("", payload, {"token_rotation_enabled": True})
        assert "token_without_expiry" not in result.misuse_patterns
        assert "long_lived_token" not in result.misuse_patterns


class TestCredentialDetector:
    def _make_finding(self, rule_id: str, severity: int = 4) -> TextFinding:
        return TextFinding(
            rule_id=rule_id, category="regex", severity=severity,
            weight=20.0, evidence="test evidence",
        )

    def test_detect_bearer_token(self) -> None:
        txt = TextScanResult(
            findings=[self._make_finding("saas_bearer_token", 5)],
            total_score=80.0, matched_count=1,
        )
        result = detect_credential_exposure(txt)
        assert result.exposed_credentials == 1
        assert "bearer_token_exposed" in result.exposure_types

    def test_detect_multiple_types(self) -> None:
        txt = TextScanResult(
            findings=[
                self._make_finding("saas_bearer_token", 5),
                self._make_finding("saas_api_key_assignment", 5),
            ],
            total_score=90.0, matched_count=2,
        )
        result = detect_credential_exposure(txt)
        assert result.exposed_credentials == 2
        assert len(result.exposure_types) == 2

    def test_no_credentials_returns_empty(self) -> None:
        txt = TextScanResult(findings=[], total_score=0.0, matched_count=0)
        result = detect_credential_exposure(txt)
        assert result.exposed_credentials == 0

    def test_count_credential_findings(self) -> None:
        findings = [
            self._make_finding("saas_bearer_token"),
            self._make_finding("some_other_rule"),
            self._make_finding("saas_api_key_assignment"),
        ]
        assert count_credential_exposure_findings(findings) == 2


class TestDataFlowRisk:
    def test_cross_platform_sensitive_data(self) -> None:
        payload = {
            "source_app": "salesforce",
            "destination_app": "slack",
            "data_types": ["pii", "customer_data"],
        }
        result = analyze_data_flow(payload)
        assert result.cross_platform_risk is True
        assert result.sensitive_data_exposed is True
        assert result.flow_risk_score > 0

    def test_same_app_no_cross_platform(self) -> None:
        payload = {
            "source_app": "slack",
            "destination_app": "slack",
            "data_types": ["pii"],
        }
        result = analyze_data_flow(payload)
        assert result.cross_platform_risk is False

    def test_no_sensitive_data_low_risk(self) -> None:
        payload = {
            "source_app": "jira",
            "destination_app": "confluence",
            "data_types": ["comments"],
        }
        result = analyze_data_flow(payload)
        assert result.sensitive_data_exposed is False


class TestCompositeRiskScoring:
    def test_high_risk_produces_high_score(self) -> None:
        signals = SaaSSignalSummary(
            oauth=OAuthAnalysis(scope_risk_score=90.0, over_permissioned=True),
            tokens=TokenAnalysis(token_risk_score=80.0),
            credentials=CredentialExposure(credential_risk_score=70.0),
            data_flow=DataFlowRisk(flow_risk_score=60.0),
        )
        score = compute_composite_score(signals)
        assert score >= 60.0

    def test_low_risk_produces_low_score(self) -> None:
        signals = SaaSSignalSummary(
            oauth=OAuthAnalysis(scope_risk_score=0.0),
            tokens=TokenAnalysis(token_risk_score=0.0),
            credentials=CredentialExposure(credential_risk_score=0.0),
            data_flow=DataFlowRisk(flow_risk_score=0.0),
        )
        score = compute_composite_score(signals)
        assert score == 0.0

    def test_risk_level_classification(self) -> None:
        assert risk_level_from_score(85) == "CRITICAL"
        assert risk_level_from_score(65) == "HIGH"
        assert risk_level_from_score(45) == "MEDIUM"
        assert risk_level_from_score(25) == "LOW"
        assert risk_level_from_score(10) == "MINIMAL"
