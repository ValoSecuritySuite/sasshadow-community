"""Shared risk scoring engine.

Generates a composite risk score (0–100) from analyzer results using
configurable dimension weights. Used by all analyzers and the pipeline.

Weights (spec):
  - OAuth Scope Risk:    30%
  - Token Misuse:        25%
  - Credential Exposure: 35%
  - Data Flow Risk:      10%
"""

from __future__ import annotations

from typing import Any

from app.models.scan_models import (
    RiskLevel,
    SaaSSignalSummary,
    TextFinding,
)

# ── Risk category weights (must sum to 1.0) ─────────────────────────────────
# OAuth 30, Token Misuse 25, Credential Exposure 35, Data Flow 10
WEIGHTS = {
    "oauth": 0.30,
    "tokens": 0.25,
    "credentials": 0.35,
    "data_flow": 0.10,
}


def compute_composite_score(signals: SaaSSignalSummary) -> float:
    """Compute weighted composite risk score (0–100) from analyzer dimensions.

    Formula: sum(dimension_score * weight) for each category, with
    severity ceilings so critical/high dimensions enforce minimum scores.
    """
    dimension_scores = {
        "oauth": signals.oauth.scope_risk_score,
        "tokens": signals.tokens.token_risk_score,
        "credentials": signals.credentials.credential_risk_score,
        "data_flow": signals.data_flow.flow_risk_score,
    }

    weighted = sum(
        dimension_scores[dim] * WEIGHTS[dim]
        for dim in dimension_scores
    )

    max_dim_score = max(dimension_scores.values()) if dimension_scores else 0.0
    if max_dim_score >= 80.0 and weighted < 60.0:
        weighted = 60.0
    elif max_dim_score >= 60.0 and weighted < 40.0:
        weighted = 40.0

    return round(min(100.0, weighted), 2)


def risk_level_from_score(score: float) -> RiskLevel:
    """Map numeric risk score to severity label."""
    if score >= 80:
        return "CRITICAL"
    if score >= 60:
        return "HIGH"
    if score >= 40:
        return "MEDIUM"
    if score >= 20:
        return "LOW"
    return "MINIMAL"


def get_dimension_scores(signals: SaaSSignalSummary) -> dict[str, float]:
    """Return per-dimension scores for transparency."""
    return {
        "oauth_scope_risk": round(signals.oauth.scope_risk_score, 2),
        "token_misuse": round(signals.tokens.token_risk_score, 2),
        "credential_exposure": round(signals.credentials.credential_risk_score, 2),
        "data_flow_risk": round(signals.data_flow.flow_risk_score, 2),
    }


def compute_risk_summary(
    integration: str,
    signals: SaaSSignalSummary,
    risk_score: float,
    findings: list[TextFinding] | None = None,
) -> dict[str, Any]:
    """Build structured risk summary for API/report output.

    Example output:
      {
        "integration": "GitHub-Jira",
        "risk_score": 72,
        "severity": "High",
        "findings": [...],
        "dimension_scores": { "oauth_scope_risk": 45, ... },
        "weights": { "oauth": 0.30, ... }
      }
    """
    severity = risk_level_from_score(risk_score)
    dimension_scores = get_dimension_scores(signals)
    return {
        "integration": integration,
        "risk_score": risk_score,
        "severity": severity,
        "findings": [f.model_dump() for f in (findings or [])],
        "dimension_scores": dimension_scores,
        "weights": dict(WEIGHTS),
    }
