"""Domain models for SaaS integration scanning.

These Pydantic models represent the core data structures that flow through
the SaaSShadow analysis pipeline — from raw integration input through risk
scoring to final reporting.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

# ── Enumerations ──────────────────────────────────────────────────────────────

InputKind = Literal["text", "json", "bytes"]
PatternOp = Literal[
    "eq", "neq", "in", "not_in", "contains", "not_contains",
    "gte", "lte", "gt", "lt", "matches", "exists", "not_exists",
]
TextScanRuleCategory = Literal["regex", "keyword", "entropy"]
RiskLevel = Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "MINIMAL"]

# ── Generic API models ────────────────────────────────────────────────────────


class ErrorDetail(BaseModel):
    code: str = Field(description="Error code")
    message: str = Field(description="Human-readable message")
    detail: dict[str, Any] | None = Field(default=None)


class ErrorResponse(BaseModel):
    error: ErrorDetail


class HealthResponse(BaseModel):
    status: str


# ── YAML Policy Rule models ──────────────────────────────────────────────────


class Pattern(BaseModel):
    model_config = ConfigDict(extra="ignore")
    field: str = Field(min_length=1, description="Context field path")
    op: PatternOp
    value: Any | None = Field(default=None)


class Rule(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str = Field(min_length=1)
    severity: int = Field(ge=1, le=5)
    weight: float = Field(gt=0)
    enabled: bool = True
    patterns: List[Pattern] = Field(default_factory=list)


class TextScanRule(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(min_length=1)
    category: TextScanRuleCategory
    pattern: str = Field(default="")
    severity: int = Field(ge=1, le=5)
    weight: float = Field(gt=0)
    enabled: bool = True
    description: Optional[str] = Field(default=None)

    @model_validator(mode="after")
    def _validate_pattern_for_category(self) -> "TextScanRule":
        if self.category in ("regex", "keyword") and not self.pattern:
            raise ValueError(
                f"Rule '{self.id}': 'pattern' must not be empty for category '{self.category}'"
            )
        return self


class RuleSet(BaseModel):
    rules: List[Rule] = Field(default_factory=list)
    text_scan_rules: List[TextScanRule] = Field(default_factory=list)


class RuleSetResponse(BaseModel):
    rules: List[Rule]
    text_scan_rules: List[TextScanRule] = Field(default_factory=list)
    rules_info: Optional[RulesInfo] = Field(default=None)


class RuleMatch(BaseModel):
    rule_name: str
    severity: int
    weight: float
    matched: bool


class RuleEngineResult(BaseModel):
    matched_rules: List[RuleMatch] = Field(default_factory=list)
    total_score: float = Field(default=0.0, ge=0)
    passed_count: int = Field(default=0, ge=0)
    failed_count: int = Field(default=0, ge=0)


class RuleEvalRequest(BaseModel):
    context: dict[str, Any] = Field(default_factory=dict)


# ── Text-scan finding models ─────────────────────────────────────────────────


class TextFinding(BaseModel):
    rule_id: str
    category: str
    severity: int = Field(ge=1, le=5)
    weight: float
    evidence: str
    match_start: Optional[int] = Field(default=None)
    match_end: Optional[int] = Field(default=None)


class TextScanResult(BaseModel):
    findings: List[TextFinding] = Field(default_factory=list)
    total_score: float = Field(default=0.0, ge=0)
    matched_count: int = Field(default=0, ge=0)


# ── Normalizer & Detection ───────────────────────────────────────────────────


class NormalizedInput(BaseModel):
    target: str = Field(default="unknown")
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    input_kind: InputKind = Field(default="text")
    content_length: int = Field(ge=0)
    encoding: Optional[str] = Field(default=None)


class DetectionFlags(BaseModel):
    content_type: str = Field(default="text")
    detected_language: Optional[str] = Field(default=None)
    token_count: int = Field(default=0, ge=0)
    line_count: int = Field(default=0, ge=0)
    flags: List[str] = Field(default_factory=list)


# ── OAuth & SaaS-specific signal models ──────────────────────────────────────


class OAuthScopeRisk(BaseModel):
    """Risk assessment for a single OAuth scope."""
    scope: str
    risk_level: RiskLevel = "MINIMAL"
    severity: int = Field(default=1, ge=1, le=5)
    description: str = ""
    is_wildcard: bool = False


class OAuthAnalysis(BaseModel):
    """Complete OAuth scope analysis result."""
    total_scopes: int = Field(default=0, ge=0)
    scopes: List[str] = Field(default_factory=list)
    high_risk_scopes: List[OAuthScopeRisk] = Field(default_factory=list)
    wildcard_scopes: List[str] = Field(default_factory=list)
    safe_scopes: List[str] = Field(default_factory=list)
    over_permissioned: bool = False
    scope_risk_score: float = Field(default=0.0, ge=0, le=100)


class TokenAnalysis(BaseModel):
    """API token entropy and exposure analysis result."""
    tokens_found: int = Field(default=0, ge=0)
    misuse_patterns: List[str] = Field(default_factory=list)
    high_entropy_tokens: int = Field(default=0, ge=0)
    weak_tokens: int = Field(default=0, ge=0)
    tokens_in_urls: int = Field(default=0, ge=0)
    long_lived_tokens: int = Field(default=0, ge=0)
    rotation_disabled: bool = False
    shared_across_integrations: bool = False
    token_risk_score: float = Field(default=0.0, ge=0, le=100)


class CredentialFinding(BaseModel):
    """Single credential exposure finding from the credential scanner.

    Example: Type=AWS Access Key, Risk=Critical, Location=config.yaml
    """
    credential_type: str = Field(description="Detected pattern type (e.g. AWS Access Key, OAuth Token)")
    risk: RiskLevel = Field(description="Risk level: CRITICAL, HIGH, MEDIUM, LOW, MINIMAL")
    location: str = Field(default="", description="Artifact or line reference (e.g. config.yaml, line 12)")
    evidence: str = Field(default="", description="Redacted or truncated match for display")
    match_start: Optional[int] = Field(default=None)
    match_end: Optional[int] = Field(default=None)
    severity: int = Field(default=4, ge=1, le=5)
    detection_method: Literal["regex", "entropy"] = Field(default="regex")
    integration_context: Optional[dict[str, Any]] = Field(
        default=None,
        description="Affected integration: target, source_app, destination_app",
    )


class CredentialExposure(BaseModel):
    """Credential exposure detection result."""
    exposed_credentials: int = Field(default=0, ge=0)
    exposure_types: List[str] = Field(default_factory=list)
    findings: List[TextFinding] = Field(default_factory=list)
    credential_risk_score: float = Field(default=0.0, ge=0, le=100)
    credential_scan_findings: List[CredentialFinding] = Field(
        default_factory=list,
        description="Structured findings from the credential exposure scanner (Type, Risk, Location)",
    )


class DataFlowRisk(BaseModel):
    """SaaS-to-SaaS data flow risk mapping."""
    source_app: Optional[str] = None
    destination_app: Optional[str] = None
    data_types: List[str] = Field(default_factory=list)
    sensitive_data_exposed: bool = False
    cross_platform_risk: bool = False
    flow_risk_score: float = Field(default=0.0, ge=0, le=100)


class SaaSSignalSummary(BaseModel):
    """Aggregated SaaS integration risk signals."""
    oauth: OAuthAnalysis = Field(default_factory=OAuthAnalysis)
    tokens: TokenAnalysis = Field(default_factory=TokenAnalysis)
    credentials: CredentialExposure = Field(default_factory=CredentialExposure)
    data_flow: DataFlowRisk = Field(default_factory=DataFlowRisk)


class RiskSummary(BaseModel):
    """Structured risk summary from the shared scoring engine.

    Example: integration=GitHub-Jira, risk_score=72, severity=High, findings=[...]
    """
    integration: str = Field(default="", description="Integration identifier")
    risk_score: float = Field(ge=0, le=100, description="Composite 0-100 risk score")
    severity: RiskLevel = Field(description="Risk level label")
    findings: List[TextFinding] = Field(default_factory=list)
    dimension_scores: dict[str, float] = Field(
        default_factory=dict,
        description="Per-dimension scores: oauth_scope_risk, token_misuse, credential_exposure, data_flow_risk",
    )
    weights: dict[str, float] = Field(
        default_factory=dict,
        description="Weights used: oauth, tokens, credentials, data_flow",
    )


# ── Report models ─────────────────────────────────────────────────────────────


class ContextRuleSummary(BaseModel):
    name: str
    severity: int
    weight: float
    enabled: bool
    pattern_count: int


class TextScanRuleSummary(BaseModel):
    id: str
    category: str
    severity: int
    weight: float
    enabled: bool
    description: Optional[str] = None


class RulesInfo(BaseModel):
    filename: str
    filepath: str
    context_rule_count: int = Field(ge=0)
    text_scan_rule_count: int = Field(ge=0)
    total_rule_count: int = Field(ge=0)
    context_rules: List[ContextRuleSummary] = Field(default_factory=list)
    text_scan_rules: List[TextScanRuleSummary] = Field(default_factory=list)


class ScanReport(BaseModel):
    scan_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    risk_score: float = Field(ge=0, description="Composite 0-100 risk score")
    risk_level: RiskLevel = "MINIMAL"
    max_severity_found: int = Field(default=0, ge=0)
    severity_ceiling_applied: bool = Field(default=False)
    risk_summary: Optional[dict[str, Any]] = Field(
        default=None,
        description="Structured risk summary (integration, risk_score, severity, findings, dimension_scores, weights)",
    )
    oauth_analysis: Optional[OAuthAnalysis] = Field(default=None)
    token_analysis: Optional[TokenAnalysis] = Field(default=None)
    credential_exposure: Optional[CredentialExposure] = Field(default=None)
    data_flow_risk: Optional[DataFlowRisk] = Field(default=None)
    findings: List[TextFinding] = Field(default_factory=list)
    matched_rules: List[RuleMatch] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    # Enhanced reporting (enterprise / governance)
    executive_summary: Optional[dict[str, Any]] = Field(
        default=None,
        description="Structured executive summary (narrative, metrics)",
    )
    integration_visibility_summary: Optional[dict[str, Any]] = Field(
        default=None,
        description="Integration map summary (systems, links, connection types)",
    )
    top_risky_connections: List[dict[str, Any]] = Field(
        default_factory=list,
        description="Top risky SaaS connections (source, target, risk_score)",
    )
    ai_data_flow_risks: Optional[dict[str, Any]] = Field(
        default=None,
        description="AI-related data flow risks (findings_count, shadow_ai, remediation hints)",
    )
    compliance_mapping: List[dict[str, Any]] = Field(
        default_factory=list,
        description="Findings mapped to SOC 2, ISO 27001, NIST AI RMF (framework, control, remediation)",
    )
    remediation_recommendations: List[dict[str, Any]] = Field(
        default_factory=list,
        description="Prioritized remediation recommendations (title, body, priority)",
    )
    risk_graph: Optional[dict[str, Any]] = Field(
        default=None,
        description="Graph model (nodes, edges) for UI or export",
    )
    # Enterprise security report sections (full analysis context)
    analyzed_input_overview: Optional[dict[str, Any]] = Field(
        default=None,
        description="Target, source/destination, auth type, format, content stats, sanitized preview",
    )
    integration_metadata: Optional[dict[str, Any]] = Field(
        default=None,
        description="Integration purpose, provider, data types, token rotation, etc.",
    )
    detection_signals: Optional[dict[str, Any]] = Field(
        default=None,
        description="Signals discovered during scanning (flags, descriptions)",
    )
    analyzer_breakdown: Optional[dict[str, Any]] = Field(
        default=None,
        description="OAuth, token, credential, data flow analyzer results",
    )
    risk_graph_summary: Optional[dict[str, Any]] = Field(
        default=None,
        description="Nodes, edges, highest risk edge, findings on edge",
    )
    dataset_context: Optional[dict[str, Any]] = Field(
        default=None,
        description="Dataset name and stats when scan is from batch run",
    )
    pipeline_trace: Optional[list[str]] = Field(
        default=None,
        description="Analysis pipeline steps executed",
    )
    attack_scenario: Optional[dict[str, Any]] = Field(
        default=None,
        description="Potential attack scenario and impact",
    )


# ── Pipeline request / result ────────────────────────────────────────────────


class ScanInput(BaseModel):
    target: str = Field(min_length=1)
    content: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PipelineRequest(BaseModel):
    text: Optional[str] = Field(default=None, description="Raw text / config content to scan")
    json_data: Optional[dict[str, Any]] = Field(default=None, description="Structured SaaS integration JSON")
    target: str = Field(default="pipeline", description="Integration identifier")
    metadata: dict[str, Any] = Field(default_factory=dict)
    customer_id: Optional[str] = Field(default=None, description="Optional customer/tenant id for scan history")

    @model_validator(mode="after")
    def _at_least_one_input(self) -> "PipelineRequest":
        if self.text is None and self.json_data is None:
            raise ValueError("Provide at least one of 'text' or 'json_data'")
        return self


class PipelineResult(BaseModel):
    normalized: NormalizedInput
    detection: DetectionFlags
    matched_rules: List[RuleMatch] = Field(default_factory=list)
    context_score: float = Field(default=0.0, ge=0)
    passed_count: int = Field(default=0, ge=0)
    failed_count: int = Field(default=0, ge=0)
    text_findings: List[TextFinding] = Field(default_factory=list)
    text_scan_score: float = Field(default=0.0, ge=0)
    text_matched_count: int = Field(default=0, ge=0)
    saas_signals: SaaSSignalSummary = Field(default_factory=SaaSSignalSummary)
    combined_score: float = Field(default=0.0, ge=0, description="Composite risk score 0-100")
    risk_summary: Optional[dict[str, Any]] = Field(
        default=None,
        description="Structured risk summary from core risk engine (integration, risk_score, severity, findings, dimension_scores)",
    )
    report: Optional[ScanReport] = Field(default=None)


class PdfRequest(BaseModel):
    title: str = Field(min_length=1)
    lines: List[str] = Field(default_factory=list, max_length=50)


class ScanInputResponse(BaseModel):
    accepted: bool
    target: str
    content_length: int
    message: str
    matched_rules: List[RuleMatch] = Field(default_factory=list)
    total_score: float = Field(default=0.0, ge=0)
    passed_count: int = Field(default=0, ge=0)
    failed_count: int = Field(default=0, ge=0)
    text_findings: List[TextFinding] = Field(default_factory=list)
    text_scan_score: float = Field(default=0.0, ge=0)
    text_matched_count: int = Field(default=0, ge=0)
    report: Optional[ScanReport] = Field(default=None)


# ── Dataset (batch) analysis ──────────────────────────────────────────────────


class DatasetItemRequest(BaseModel):
    integration_id: str = Field(min_length=1)
    text: Optional[str] = Field(default=None)
    json_data: Optional[dict[str, Any]] = Field(default=None)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _at_least_one_input(self) -> "DatasetItemRequest":
        if self.text is None and self.json_data is None:
            raise ValueError("Provide at least one of 'text' or 'json_data'")
        return self


class DatasetAnalysisRequest(BaseModel):
    dataset_name: str = Field(default="sample_saas_integration_dataset")
    items: List[DatasetItemRequest] = Field(min_length=1)


class DatasetItemResult(BaseModel):
    integration_id: str
    risk_score: float = Field(ge=0)
    risk_level: RiskLevel = "MINIMAL"
    oauth_over_permission_detected: bool
    token_misuse_detected: bool
    credential_exposure_detected: bool
    cross_platform_risk_detected: bool = False
    report: ScanReport


class DatasetAnalysisSummary(BaseModel):
    total_integrations: int = Field(ge=0)
    high_risk_integrations: int = Field(ge=0)
    average_risk_score: float = Field(ge=0)
    oauth_over_permission_hits: int = Field(ge=0)
    token_misuse_hits: int = Field(ge=0)
    credential_exposure_hits: int = Field(ge=0)
    cross_platform_risk_hits: int = Field(ge=0)


class DatasetAnalysisResponse(BaseModel):
    dataset_name: str
    summary: DatasetAnalysisSummary
    results: List[DatasetItemResult] = Field(default_factory=list)


# ── Scan history (persisted scans) ────────────────────────────────────────────


class KeyFindingSummary(BaseModel):
    """Minimal finding summary for scan history."""

    rule_id: str = ""
    category: str = ""
    severity: int = 0
    evidence: str = ""


class ScanListItem(BaseModel):
    """Single scan in list view (GET /scans)."""

    id: str
    target: str
    timestamp: str
    score: float
    risk_level: str
    customer_id: Optional[str] = None
    findings_count: int = 0


class ScanDetail(BaseModel):
    """Single scan detail (GET /scans/{id})."""

    id: str
    target: str
    timestamp: str
    score: float
    risk_level: str
    customer_id: Optional[str] = None
    key_findings: List[KeyFindingSummary] = Field(default_factory=list)


class ScanListResponse(BaseModel):
    """Response for GET /scans."""

    scans: List[ScanListItem] = Field(default_factory=list)


class ScanCompareResponse(BaseModel):
    """Response for GET /scans/compare — trend/diff between two scans."""

    target: str = Field(description="Integration target name")
    before_scan_id: str = Field(description="Older scan id")
    after_scan_id: str = Field(description="Newer scan id")
    timestamp_before: str = Field(description="Older scan timestamp")
    timestamp_after: str = Field(description="Newer scan timestamp")
    score_before: float = Field(description="Risk score of older scan")
    score_after: float = Field(description="Risk score of newer scan")
    score_delta: float = Field(description="score_after - score_before (positive = risk increased)")
    risk_level_before: str = ""
    risk_level_after: str = ""
    new_findings: List[KeyFindingSummary] = Field(
        default_factory=list,
        description="Findings in newer scan not in older (regressions)",
    )
    mitigated_findings: List[KeyFindingSummary] = Field(
        default_factory=list,
        description="Findings in older scan not in newer (fixed)",
    )
