"""Tests for the shared risk scoring engine (app/core/risk_engine)."""


from app.core.risk_engine import (
    WEIGHTS,
    compute_composite_score,
    compute_risk_summary,
    get_dimension_scores,
    risk_level_from_score,
)
from app.models.scan_models import (
    CredentialExposure,
    DataFlowRisk,
    OAuthAnalysis,
    SaaSSignalSummary,
    TextFinding,
    TokenAnalysis,
)


class TestWeights:
    """Scoring weights match spec: OAuth 30, Token 25, Credential 35, Data Flow 10."""

    def test_weights_sum_to_one(self) -> None:
        assert sum(WEIGHTS.values()) == 1.0

    def test_weights_match_spec(self) -> None:
        assert WEIGHTS["oauth"] == 0.30
        assert WEIGHTS["tokens"] == 0.25
        assert WEIGHTS["credentials"] == 0.35
        assert WEIGHTS["data_flow"] == 0.10


class TestComputeCompositeScore:
    """Composite score aggregation."""

    def test_zero_signals_zero_score(self) -> None:
        signals = SaaSSignalSummary()
        assert compute_composite_score(signals) == 0.0

    def test_credential_heavy_weight(self) -> None:
        signals = SaaSSignalSummary(
            oauth=OAuthAnalysis(scope_risk_score=0),
            tokens=TokenAnalysis(token_risk_score=0),
            credentials=CredentialExposure(credential_risk_score=100),
            data_flow=DataFlowRisk(flow_risk_score=0),
        )
        score = compute_composite_score(signals)
        # 100 * 0.35 = 35, but severity ceiling (dim >= 80) raises to at least 60
        assert score >= 35.0
        assert score == 60.0

    def test_all_dimensions_weighted(self) -> None:
        signals = SaaSSignalSummary(
            oauth=OAuthAnalysis(scope_risk_score=50),
            tokens=TokenAnalysis(token_risk_score=50),
            credentials=CredentialExposure(credential_risk_score=50),
            data_flow=DataFlowRisk(flow_risk_score=50),
        )
        score = compute_composite_score(signals)
        assert score == 50.0

    def test_severity_ceiling_critical(self) -> None:
        signals = SaaSSignalSummary(
            oauth=OAuthAnalysis(scope_risk_score=0),
            tokens=TokenAnalysis(token_risk_score=0),
            credentials=CredentialExposure(credential_risk_score=90),
            data_flow=DataFlowRisk(flow_risk_score=0),
        )
        score = compute_composite_score(signals)
        assert score >= 60.0

    def test_score_capped_at_100(self) -> None:
        signals = SaaSSignalSummary(
            oauth=OAuthAnalysis(scope_risk_score=100),
            tokens=TokenAnalysis(token_risk_score=100),
            credentials=CredentialExposure(credential_risk_score=100),
            data_flow=DataFlowRisk(flow_risk_score=100),
        )
        assert compute_composite_score(signals) == 100.0


class TestRiskLevelFromScore:
    """Severity label mapping."""

    def test_critical(self) -> None:
        assert risk_level_from_score(80) == "CRITICAL"
        assert risk_level_from_score(100) == "CRITICAL"

    def test_high(self) -> None:
        assert risk_level_from_score(60) == "HIGH"
        assert risk_level_from_score(79) == "HIGH"

    def test_medium(self) -> None:
        assert risk_level_from_score(40) == "MEDIUM"
        assert risk_level_from_score(59) == "MEDIUM"

    def test_low(self) -> None:
        assert risk_level_from_score(20) == "LOW"
        assert risk_level_from_score(39) == "LOW"

    def test_minimal(self) -> None:
        assert risk_level_from_score(0) == "MINIMAL"
        assert risk_level_from_score(19) == "MINIMAL"


class TestComputeRiskSummary:
    """Structured risk summary (integration, risk_score, severity, findings)."""

    def test_summary_structure(self) -> None:
        signals = SaaSSignalSummary(
            credentials=CredentialExposure(credential_risk_score=70),
        )
        summary = compute_risk_summary("GitHub-Jira", signals, 72.0, [])
        assert summary["integration"] == "GitHub-Jira"
        assert summary["risk_score"] == 72
        assert summary["severity"] == "HIGH"
        assert "findings" in summary
        assert "dimension_scores" in summary
        assert "weights" in summary
        assert summary["dimension_scores"]["credential_exposure"] == 70.0
        assert summary["weights"]["credentials"] == 0.35

    def test_summary_includes_findings(self) -> None:
        findings = [
            TextFinding(
                rule_id="credential_api_key",
                category="regex",
                severity=5,
                weight=24.0,
                evidence="api_key=sk_***",
            ),
        ]
        signals = SaaSSignalSummary()
        summary = compute_risk_summary("test", signals, 65.0, findings)
        assert len(summary["findings"]) == 1
        assert summary["findings"][0]["rule_id"] == "credential_api_key"


class TestGetDimensionScores:
    """Per-dimension score extraction."""

    def test_returns_all_four_dimensions(self) -> None:
        signals = SaaSSignalSummary(
            oauth=OAuthAnalysis(scope_risk_score=10),
            tokens=TokenAnalysis(token_risk_score=20),
            credentials=CredentialExposure(credential_risk_score=30),
            data_flow=DataFlowRisk(flow_risk_score=40),
        )
        dims = get_dimension_scores(signals)
        assert dims["oauth_scope_risk"] == 10.0
        assert dims["token_misuse"] == 20.0
        assert dims["credential_exposure"] == 30.0
        assert dims["data_flow_risk"] == 40.0
