"""Pydantic DTOs for the basic dashboard (Community Edition).

Each model mirrors a single /dashboard/* endpoint response shape. The
service layer (:mod:`app.services.dashboard_metrics`) produces these
DTOs from the scan-history store; the API layer
(:mod:`app.api.dashboard`) just streams them.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.scan_models import RiskLevel


TrendBucket = Literal["hour", "day", "week"]


# ── Overview KPI tiles ──────────────────────────────────────────────────────


class DashboardOverview(BaseModel):
    """Top-of-page KPI summary derived from scan history."""

    model_config = ConfigDict(extra="ignore")

    window_days: int = Field(ge=0, description="Rolling window in days (0 = all-time)")
    scans_total: int = Field(ge=0, description="Total scans ever stored")
    scans_in_window: int = Field(ge=0, description="Scans completed inside the window")
    integrations_tracked: int = Field(
        ge=0, description="Distinct SaaS integrations ever observed"
    )
    integrations_in_window: int = Field(
        ge=0, description="Distinct integrations scanned inside the window"
    )
    avg_risk_score: float = Field(
        ge=0.0,
        description="Mean risk_score across the latest scan per integration inside the window",
    )
    median_risk_score: float = Field(
        ge=0.0,
        description="Median risk_score across the latest scan per integration",
    )
    portfolio_risk_level: RiskLevel = Field(
        default="MINIMAL",
        description="Risk level derived from avg_risk_score (board-friendly headline)",
    )
    critical_integrations: int = Field(
        ge=0,
        description="Integrations whose latest scan is CRITICAL or HIGH",
    )
    risk_delta_vs_prior_window: float = Field(
        description="avg_risk_score(this window) - avg_risk_score(prior equally-sized window)",
    )
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Server timestamp when this overview was computed",
    )


# ── Risk trend (time series) ────────────────────────────────────────────────


class RiskTrendPoint(BaseModel):
    model_config = ConfigDict(extra="ignore")

    bucket_start: datetime = Field(description="UTC start of the bucket")
    avg_risk_score: float = Field(ge=0.0)
    max_risk_score: float = Field(ge=0.0)
    scans: int = Field(ge=0, description="Scans contained in this bucket")


class RiskTrendResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    window_days: int = Field(ge=0)
    bucket: TrendBucket
    points: List[RiskTrendPoint] = Field(default_factory=list)


# ── Risk distribution (latest per integration) ──────────────────────────────


class RiskDistributionEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")

    risk_level: RiskLevel
    count: int = Field(
        ge=0, description="Integrations whose latest scan falls into this bucket"
    )


class RiskDistribution(BaseModel):
    model_config = ConfigDict(extra="ignore")

    total_integrations: int = Field(ge=0)
    entries: List[RiskDistributionEntry] = Field(default_factory=list)


# ── Critical findings ───────────────────────────────────────────────────────


class CriticalFindingEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")

    scan_id: str
    target: str
    customer_id: str | None = None
    created_at: datetime
    risk_score: float = Field(ge=0.0)
    risk_level: RiskLevel
    rule_id: str | None = None
    category: str | None = None
    severity: int = Field(ge=0, le=5)
    summary: str = Field(description="One-line board-friendly description")


class CriticalFindingsResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    limit: int = Field(ge=1)
    findings: List[CriticalFindingEntry] = Field(default_factory=list)


__all__ = [
    "CriticalFindingEntry",
    "CriticalFindingsResponse",
    "DashboardOverview",
    "RiskDistribution",
    "RiskDistributionEntry",
    "RiskTrendPoint",
    "RiskTrendResponse",
    "TrendBucket",
]
