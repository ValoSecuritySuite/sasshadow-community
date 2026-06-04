"""Enterprise SaaS risk graph layer.

Builds a graph-friendly representation for UI or export:
- Nodes = SaaS platforms / AI systems
- Edges = integrations / data flows
- Edge attributes = risk score, connection type, findings, severity

Output is JSON-serializable (Pydantic models) for use in reports and APIs.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.analysis.integration_mapper import IntegrationMap


class GraphNode(BaseModel):
    """A node in the risk graph (SaaS platform or AI system)."""

    id: str = Field(description="Unique node identifier (lowercase, normalized)")
    label: str = Field(description="Display label")
    node_type: str = Field(default="saas", description="saas | ai | connector")
    risk_score: float = Field(default=0.0, ge=0, le=100, description="Aggregate risk for this node if known")


class GraphEdge(BaseModel):
    """An edge in the risk graph (integration or data flow)."""

    source: str = Field(description="Source node id")
    target: str = Field(description="Target node id")
    risk_score: float = Field(default=0.0, ge=0, le=100)
    connection_type: str = Field(default="unknown", description="oauth | api | webhook | connector | workflow")
    direction: str = Field(default="outbound", description="inbound | outbound | bidirectional")
    severity: int = Field(default=1, ge=1, le=5, description="Max severity of associated findings")
    findings_count: int = Field(default=0, ge=0)
    findings_summary: list[str] = Field(default_factory=list, description="Short finding evidence or rule IDs")
    data_types: list[str] = Field(default_factory=list)


class RiskGraph(BaseModel):
    """Graph-friendly representation for enterprise SaaS risk.

    Suitable for JSON export and later use in UI or graph visualization.
    """

    integration_id: str = Field(default="", description="Scan or batch identifier")
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    max_severity: int = Field(default=0, ge=0, le=5)
    total_risk_score: float = Field(default=0.0, ge=0, le=100)


def build_risk_graph(
    integration_map: IntegrationMap,
    risk_score: float = 0.0,
    findings: list[Any] | None = None,
    max_severity: int = 0,
) -> RiskGraph:
    """Build a risk graph from an integration map and scan results.

    Args:
        integration_map: Output from integration_mapper.map_integrations().
        risk_score: Composite risk score (0–100) for this integration.
        findings: Optional list of TextFinding-like dicts or objects with
                  rule_id, severity, evidence (used for edge findings_summary).
        max_severity: Optional max severity (1–5) across findings.

    Returns:
        RiskGraph with nodes (from systems), edges (from links), and
        edge attributes (risk_score, connection_type, findings, severity).
    """
    findings = findings or []
    finding_list = []
    for f in findings:
        if hasattr(f, "model_dump"):
            finding_list.append(f.model_dump() if callable(getattr(f, "model_dump")) else {})
        elif isinstance(f, dict):
            finding_list.append(f)
        else:
            finding_list.append({"rule_id": getattr(f, "rule_id", ""), "severity": getattr(f, "severity", 1), "evidence": getattr(f, "evidence", "")})

    # Build nodes from integration_map.systems (+ mark AI if present)
    ai_indicators = {"openai", "anthropic", "claude", "copilot", "gemini", "llm", "vertex ai"}
    nodes: list[GraphNode] = []
    seen_nodes: set[str] = set()
    for sys in integration_map.systems:
        if not sys or sys in seen_nodes:
            continue
        seen_nodes.add(sys)
        node_type = "ai" if any(ai in sys for ai in ai_indicators) else "saas"
        nodes.append(GraphNode(id=sys, label=sys, node_type=node_type, risk_score=0.0))

    # If no systems but we have links, derive nodes from link endpoints
    if not nodes and integration_map.links:
        for link in integration_map.links:
            for sid in (link.source, link.target):
                if sid and sid not in seen_nodes:
                    seen_nodes.add(sid)
                    node_type = "ai" if any(ai in sid for ai in ai_indicators) else "saas"
                    nodes.append(GraphNode(id=sid, label=sid, node_type=node_type, risk_score=0.0))

    # Build edges from integration_map.links
    edges: list[GraphEdge] = []
    for link in integration_map.links:
        if not link.source and not link.target:
            continue
        src = link.source or "unknown"
        tgt = link.target or "unknown"
        if src == tgt:
            continue
        # Severity from findings if we have any; else default from risk_score band
        severity = max_severity or (4 if risk_score >= 60 else 3 if risk_score >= 40 else 2)
        summary = [(f.get("rule_id") or "") or (str(f.get("evidence") or "")[:60]) for f in finding_list[:10]]
        edges.append(
            GraphEdge(
                source=src,
                target=tgt,
                risk_score=risk_score,
                connection_type=link.link_type,
                direction=link.direction,
                severity=severity,
                findings_count=len(finding_list),
                findings_summary=summary[:5],
                data_types=list(link.data_types or []),
            )
        )

    derived_severity = max((f.get("severity", 1) for f in finding_list), default=0)
    final_max_severity = max(max_severity, derived_severity) if (max_severity or finding_list) else 0

    return RiskGraph(
        integration_id=integration_map.integration_id,
        nodes=nodes,
        edges=edges,
        max_severity=final_max_severity,
        total_risk_score=risk_score,
    )
