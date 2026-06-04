"""Domain models for the SaaS Mapping Engine and ISPM (Integration Security Posture Management).

These Pydantic models extend the per-scan IntegrationMap with a tenant-wide,
persisted map plus posture grading and category classification.

Source-of-truth tables live in ``app/db/saas_map_store.py``.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


PostureGrade = Literal["COMPLIANT", "AT_RISK", "CRITICAL"]


# --- ISPM configuration models ----------------------------------------------


class PostureThresholds(BaseModel):
    """Risk score boundaries for posture grading.

    ``compliant`` is the upper bound for COMPLIANT (inclusive), ``at_risk`` is
    the upper bound for AT_RISK (inclusive). Anything above ``at_risk`` is
    CRITICAL.
    """

    model_config = ConfigDict(extra="ignore")
    compliant: float = Field(default=30.0, ge=0, le=100)
    at_risk: float = Field(default=60.0, ge=0, le=100)


class IspmCategory(BaseModel):
    """A single ISPM category (e.g. Identity, Communication, Storage)."""

    model_config = ConfigDict(extra="ignore")
    id: str = Field(min_length=1, description="Stable category id (lowercase)")
    label: str = Field(min_length=1, description="Human-friendly label")
    description: Optional[str] = Field(default=None)
    posture_thresholds: PostureThresholds = Field(default_factory=PostureThresholds)


class IspmConfig(BaseModel):
    """Resolved ISPM configuration: defaults + DB-overlay overrides.

    Loaded from ``app/policies/ispm_categories.yaml`` and merged with any
    persisted overrides for the active customer/tenant.
    """

    model_config = ConfigDict(extra="ignore")
    categories: list[IspmCategory] = Field(default_factory=list)
    provider_map: dict[str, str] = Field(
        default_factory=dict,
        description="provider_id -> category_id",
    )
    default_category_id: str = Field(default="other")
    default_thresholds: PostureThresholds = Field(default_factory=PostureThresholds)


class IspmCategoryAssignment(BaseModel):
    """Result of classifying a single provider."""

    model_config = ConfigDict(extra="ignore")
    provider_id: str
    category_id: str
    label: str
    is_default: bool = False
    posture_thresholds: PostureThresholds = Field(default_factory=PostureThresholds)


# --- ISPM API request / response models -------------------------------------


class IspmCategoriesUpdate(BaseModel):
    """Replace category catalog and provider map."""

    model_config = ConfigDict(extra="ignore")
    categories: list[IspmCategory] = Field(min_length=1)
    provider_map: dict[str, str] = Field(default_factory=dict)
    default_category_id: str = Field(default="other")
    default_thresholds: PostureThresholds = Field(default_factory=PostureThresholds)


class IspmProviderOverride(BaseModel):
    """Override one provider->category mapping."""

    model_config = ConfigDict(extra="ignore")
    category_id: str = Field(min_length=1)


class IspmCategoriesResponse(BaseModel):
    """Active ISPM configuration."""

    config: IspmConfig
    customer_id: Optional[str] = None


class IspmProviderEntry(BaseModel):
    provider_id: str
    category_id: str
    label: str


class IspmProvidersResponse(BaseModel):
    providers: list[IspmProviderEntry] = Field(default_factory=list)


class IspmCategoryRollup(BaseModel):
    """Posture rollup for a single category."""

    category_id: str
    label: str
    integrations_count: int = Field(default=0, ge=0)
    avg_risk_score: float = Field(default=0.0, ge=0, le=100)
    grade_counts: dict[PostureGrade, int] = Field(
        default_factory=lambda: {"COMPLIANT": 0, "AT_RISK": 0, "CRITICAL": 0},
    )
    max_severity: int = Field(default=0, ge=0, le=5)


class IspmPostureResponse(BaseModel):
    """Per-category posture rollup for the tenant."""

    customer_id: Optional[str] = None
    categories: list[IspmCategoryRollup] = Field(default_factory=list)
    total_integrations: int = Field(default=0, ge=0)
    overall_grade: PostureGrade = "COMPLIANT"


class IspmIntegrationItem(BaseModel):
    """Single integration in the ISPM list view."""

    target: str
    provider_id: str
    category_id: str
    category_label: str
    risk_score: float = Field(default=0.0, ge=0, le=100)
    posture_grade: PostureGrade = "COMPLIANT"
    last_seen: str = ""
    scan_count: int = Field(default=0, ge=0)
    top_finding: Optional[str] = None


class IspmIntegrationsResponse(BaseModel):
    customer_id: Optional[str] = None
    integrations: list[IspmIntegrationItem] = Field(default_factory=list)


# --- SaaS Map models --------------------------------------------------------


class SaaSMapNode(BaseModel):
    """A single SaaS / API system in the tenant-wide map."""

    model_config = ConfigDict(extra="ignore")
    id: str = Field(description="Normalized provider id (lowercase)")
    label: str = Field(default="")
    category_id: str = Field(default="other")
    category_label: str = Field(default="Other")
    posture_grade: PostureGrade = "COMPLIANT"
    avg_risk_score: float = Field(default=0.0, ge=0, le=100)
    max_severity: int = Field(default=0, ge=0, le=5)
    scan_count: int = Field(default=0, ge=0)
    last_seen: str = ""
    targets: list[str] = Field(
        default_factory=list,
        description="Recent scan targets that referenced this node",
    )


class SaaSMapEdge(BaseModel):
    """A single SaaS-to-SaaS / SaaS-to-API connection in the tenant-wide map."""

    model_config = ConfigDict(extra="ignore")
    id: str = Field(description="Stable edge id: source|target|link_type")
    source: str
    target: str
    link_type: str = Field(default="unknown")
    direction: str = Field(default="outbound")
    risk_score: float = Field(default=0.0, ge=0, le=100)
    scan_count: int = Field(default=0, ge=0)
    scan_ids: list[str] = Field(default_factory=list)
    last_seen: str = ""


class SaaSMapSummary(BaseModel):
    """Top-level counts for the tenant map."""

    nodes_count: int = Field(default=0, ge=0)
    edges_count: int = Field(default=0, ge=0)
    integrations_count: int = Field(default=0, ge=0)
    avg_risk_score: float = Field(default=0.0, ge=0, le=100)
    grade_counts: dict[PostureGrade, int] = Field(
        default_factory=lambda: {"COMPLIANT": 0, "AT_RISK": 0, "CRITICAL": 0},
    )
    has_oauth: bool = False
    has_api: bool = False


class SaaSMap(BaseModel):
    """Tenant-wide SaaS map (aggregated from persisted scans)."""

    customer_id: Optional[str] = None
    summary: SaaSMapSummary = Field(default_factory=SaaSMapSummary)
    nodes: list[SaaSMapNode] = Field(default_factory=list)
    edges: list[SaaSMapEdge] = Field(default_factory=list)


class SaaSMapGraphNode(BaseModel):
    """Graph-friendly node for the frontend (mirrors RiskGraph.GraphNode but
    enriched with ISPM category)."""

    id: str
    label: str
    node_type: str = "saas"
    category_id: str = "other"
    category_label: str = "Other"
    posture_grade: PostureGrade = "COMPLIANT"
    risk_score: float = Field(default=0.0, ge=0, le=100)


class SaaSMapGraphEdge(BaseModel):
    source: str
    target: str
    connection_type: str = "unknown"
    direction: str = "outbound"
    risk_score: float = Field(default=0.0, ge=0, le=100)


class SaaSMapGraph(BaseModel):
    """Graph view (nodes + edges) used by the frontend visualization."""

    customer_id: Optional[str] = None
    nodes: list[SaaSMapGraphNode] = Field(default_factory=list)
    edges: list[SaaSMapGraphEdge] = Field(default_factory=list)
    max_risk_score: float = Field(default=0.0, ge=0, le=100)


class SaaSMapProvidersResponse(BaseModel):
    """Distinct providers with their resolved categories."""

    providers: list[IspmProviderEntry] = Field(default_factory=list)


class SaaSMapRefreshResponse(BaseModel):
    """Result of rebuilding the tenant map."""

    customer_id: Optional[str] = None
    nodes_written: int = 0
    edges_written: int = 0
    scans_scanned: int = 0


# --- API detection model ----------------------------------------------------


ApiProtocol = Literal["rest", "graphql", "webhook", "grpc", "openapi", "har", "postman", "soap"]
ApiAuthMode = Literal["bearer", "basic", "api_key", "oauth2", "mtls", "none", "unknown"]


class ApiEndpointDetection(BaseModel):
    """A single detected API endpoint."""

    model_config = ConfigDict(extra="ignore")
    url: str = Field(default="")
    method: str = Field(default="")
    protocol: ApiProtocol = "rest"
    auth_mode: ApiAuthMode = "unknown"
    evidence: str = Field(default="", description="Snippet showing where it was found")


class ApiDetectionResult(BaseModel):
    """Aggregate API detection output for one scan."""

    model_config = ConfigDict(extra="ignore")
    endpoints: list[ApiEndpointDetection] = Field(default_factory=list)
    protocols: list[str] = Field(default_factory=list)
    auth_modes: list[str] = Field(default_factory=list)
    has_webhook: bool = False
    has_rest: bool = False
    has_graphql: bool = False
    has_openapi: bool = False
    has_grpc: bool = False
    confidence: float = Field(default=0.0, ge=0, le=1)

    def to_metadata_dict(self) -> dict[str, Any]:
        """Compact dict for ``IntegrationMap.raw_metadata.api_detection``."""
        return {
            "endpoints_count": len(self.endpoints),
            "endpoints": [e.model_dump() for e in self.endpoints[:25]],
            "protocols": list(self.protocols),
            "auth_modes": list(self.auth_modes),
            "has_webhook": self.has_webhook,
            "has_rest": self.has_rest,
            "has_graphql": self.has_graphql,
            "has_openapi": self.has_openapi,
            "has_grpc": self.has_grpc,
            "confidence": self.confidence,
        }
