"""JSON report builder.

Assembles a :class:`ScanReport` from pipeline results, enriched with
SaaS-specific analysis (OAuth, tokens, credentials, data flow),
integration visibility, risk graph, compliance mapping, and remediation.
"""

from __future__ import annotations

import re
from typing import Any

from app.analysis.integration_mapper import IntegrationMap
from app.analysis.risk_graph import build_risk_graph
from app.compliance.framework_mapper import map_findings_to_frameworks
from app.models.scan_models import (
    DetectionFlags,
    NormalizedInput,
    PipelineResult,
    RuleSet,
    ScanInputResponse,
    ScanReport,
    TextFinding,
)
from app.services.risk_engine import cvss_combined_score, risk_level_from_score, severity_info


def _pipeline_metadata(result: PipelineResult) -> dict[str, Any]:
    norm: NormalizedInput = result.normalized
    det: DetectionFlags = result.detection
    return {
        "target": norm.target,
        "input_kind": norm.input_kind,
        "content_length": norm.content_length,
        "encoding": norm.encoding,
        "content_type": det.content_type,
        "detected_language": det.detected_language,
        "token_count": det.token_count,
        "line_count": det.line_count,
        "detection_flags": det.flags,
        "context_score": result.context_score,
        "text_scan_score": result.text_scan_score,
        "passed_count": result.passed_count,
        "failed_count": result.failed_count,
        "text_matched_count": result.text_matched_count,
        "saas_signals": result.saas_signals.model_dump(),
        **norm.metadata,
    }


def _build_executive_summary(result: PipelineResult, max_sev: int) -> dict[str, Any]:
    """Build structured executive summary for the report."""
    meta = result.normalized.metadata
    return {
        "narrative": (
            f"This report presents SaaS integration risk analysis for target "
            f"'{result.normalized.target}'. Analysis covers OAuth scope risk, token misuse, "
            "credential exposure, cross-platform data flow, and AI-related data flow risks. "
            "Scores and recommendations are derived from policy rules and heuristic analyzers."
        ),
        "metrics": {
            "risk_score": result.combined_score,
            "risk_level": (result.risk_summary or {}).get("severity", "MINIMAL"),
            "findings_count": len(result.text_findings),
            "matched_rules_count": sum(1 for r in result.matched_rules if r.matched),
            "max_severity": max_sev,
            "oauth_over_permission": result.saas_signals.oauth.over_permissioned,
            "ai_risk_detected": meta.get("ai_risk_detected", False),
        },
    }


def _sanitize_input_preview(content: str, max_lines: int = 20) -> str:
    """Return sanitized preview of input: mask credentials, limit lines."""
    if not content or not isinstance(content, str):
        return ""
    # Mask common credential patterns (value part only, keep key)
    patterns = [
        (r'(?i)(client_secret|client_secret_key|api_key|apikey|password|secret|token|access_token|refresh_token|bearer)\s*[:=]\s*["\']?[^\s"\']{8,}["\']?', r'\1: ***REDACTED***'),
        (r'(Bearer)\s+[A-Za-z0-9\-_.]{20,}', r'\1 ***REDACTED***'),
        (r'"(client_secret|api_key|password|token|access_token|refresh_token)"\s*:\s*"[^"]*"', r'"\1": "***REDACTED***"'),
    ]
    out = content
    for pat, repl in patterns:
        out = re.sub(pat, repl, out)
    lines = out.splitlines()
    if len(lines) > max_lines:
        out = "\n".join(lines[:max_lines]) + "\n..."
    return out[:2000]


def _build_analyzed_input_overview(result: PipelineResult) -> dict[str, Any]:
    """Build Analyzed Input Overview section."""
    norm = result.normalized
    det = result.detection
    meta = norm.metadata
    source = (meta.get("source_app") or result.saas_signals.data_flow.source_app or "").strip()
    dest = (meta.get("destination_app") or result.saas_signals.data_flow.destination_app or "").strip()
    auth_type = "OAuth" if (result.saas_signals.oauth.total_scopes > 0 or meta.get("oauth")) else "API/Key" if meta.get("api_key") else "Unknown"
    return {
        "target_integration": norm.target,
        "source_system": source or "—",
        "destination_system": dest or "—",
        "integration_description": meta.get("description") or "—",
        "authentication_type": auth_type,
        "input_format": (norm.input_kind or "unknown").upper(),
        "content_length": norm.content_length,
        "line_count": getattr(det, "line_count", 0) or 0,
        "token_count": getattr(det, "token_count", 0) or 0,
        "encoding": norm.encoding or "UTF-8",
        "environment": meta.get("environment") or "—",
        "input_preview": _sanitize_input_preview(norm.content),
    }


def _build_integration_metadata(result: PipelineResult) -> dict[str, Any]:
    """Build Integration Metadata section."""
    meta = result.normalized.metadata
    oauth = result.saas_signals.oauth
    tokens = result.saas_signals.tokens
    flow = result.saas_signals.data_flow
    source = (meta.get("source_app") or flow.source_app or "").strip() or "—"
    dest = (meta.get("destination_app") or flow.destination_app or "").strip() or "—"
    out = {
        "source_application": source,
        "destination_application": dest,
        "integration_purpose": meta.get("description") or "—",
        "authentication_provider": meta.get("oauth", {}).get("provider") if isinstance(meta.get("oauth"), dict) else meta.get("provider") or "—",
        "oauth_provider": meta.get("oauth", {}).get("provider") if isinstance(meta.get("oauth"), dict) else "—",
        "detected_data_types": flow.data_types or [],
        "integration_environment": meta.get("environment") or "—",
        "credential_expiry_settings": meta.get("expires_in_days") or "—",
        "token_rotation_enabled": meta.get("token_rotation_enabled", True),
        "shared_token_across_integrations": getattr(tokens, "shared_across_integrations", False),
    }
    if meta.get("user_count") is not None:
        out["user_count"] = meta["user_count"]
    if meta.get("last_used") is not None:
        out["last_used"] = meta["last_used"]
    if meta.get("last_updated") is not None:
        out["last_updated"] = meta["last_updated"]
    return out


def _build_detection_signals(result: PipelineResult) -> dict[str, Any]:
    """Build Detection Signals section with brief explanations."""
    flags = getattr(result.detection, "flags", []) or []
    meta = result.normalized.metadata
    signals_list: list[dict[str, str]] = []
    signal_descriptions = {
        "contains_secret_keyword": "Indicates presence of secret-related keywords in content.",
        "contains_base64_blob": "Base64-encoded data detected (may indicate embedded credentials).",
        "contains_high_entropy_strings": "High-entropy strings suggest possible secrets or tokens.",
        "oauth_scope_patterns_detected": "OAuth scope or permission patterns found in configuration.",
        "token_reuse_pattern_detected": "Same token value used across multiple integrations.",
        "url": "URLs present in content (may expose endpoints or tokens in query params).",
        "email": "Email addresses detected in content.",
        "ip": "IP addresses detected.",
        "ssn": "Potential SSN or national ID pattern detected.",
    }
    for f in flags:
        signals_list.append({
            "signal": f,
            "description": signal_descriptions.get(f, "Content pattern or attribute detected during scan."),
        })
    if result.saas_signals.oauth.total_scopes > 0:
        signals_list.append({"signal": "oauth_scope_patterns_detected", "description": signal_descriptions["oauth_scope_patterns_detected"]})
    if getattr(result.saas_signals.tokens, "shared_across_integrations", False):
        signals_list.append({"signal": "token_reuse_pattern_detected", "description": signal_descriptions["token_reuse_pattern_detected"]})
    return {"signals": signals_list, "count": len(signals_list)}


def _build_analyzer_breakdown(result: PipelineResult) -> dict[str, Any]:
    """Build Analyzer Results Breakdown (OAuth, Token, Credential, Data Flow)."""
    o = result.saas_signals.oauth
    t = result.saas_signals.tokens
    c = result.saas_signals.credentials
    f = result.saas_signals.data_flow
    return {
        "oauth_scope_analysis": {
            "total_scopes_detected": o.total_scopes,
            "scopes": o.scopes,
            "high_risk_scopes": [s.scope for s in o.high_risk_scopes],
            "wildcard_scopes": o.wildcard_scopes,
            "safe_scopes": o.safe_scopes,
            "over_permissioned": o.over_permissioned,
            "scope_risk_score": o.scope_risk_score,
        },
        "token_misuse_analysis": {
            "tokens_detected": t.tokens_found,
            "high_entropy_tokens": t.high_entropy_tokens,
            "weak_tokens": t.weak_tokens,
            "long_lived_tokens": t.long_lived_tokens,
            "token_reuse_across_integrations": t.shared_across_integrations,
            "token_rotation_disabled": t.rotation_disabled,
            "tokens_embedded_in_urls": t.tokens_in_urls,
            "token_risk_score": t.token_risk_score,
            "misuse_patterns": t.misuse_patterns,
        },
        "credential_exposure_analysis": {
            "total_exposed_credentials": c.exposed_credentials,
            "exposure_types": c.exposure_types,
            "credential_risk_score": c.credential_risk_score,
            "findings": [
                {
                    "credential_type": getattr(cf, "credential_type", "—"),
                    "detection_method": getattr(cf, "detection_method", "regex"),
                    "severity": getattr(cf, "risk", "—"),
                    "location": getattr(cf, "location", "—"),
                }
                for cf in (c.credential_scan_findings or [])
            ] if c.credential_scan_findings else [],
        },
        "data_flow_risk_analysis": {
            "source_saas": f.source_app or "—",
            "destination_saas": f.destination_app or "—",
            "sensitive_data_types_transmitted": f.data_types,
            "sensitive_data_exposure": f.sensitive_data_exposed,
            "cross_platform_risk_detected": f.cross_platform_risk,
            "data_flow_risk_score": f.flow_risk_score,
        },
    }


def _build_risk_graph_summary(risk_graph: dict[str, Any] | None) -> dict[str, Any] | None:
    """Build Risk Graph Summary (nodes, edges, highest risk edge)."""
    if not risk_graph:
        return None
    nodes = risk_graph.get("nodes", [])
    edges = risk_graph.get("edges", [])
    if not nodes and not edges:
        return None
    max_edge = max(edges, key=lambda e: e.get("risk_score", 0)) if edges else None
    edge_findings: list[str] = []
    if max_edge:
        edge_findings = list(max_edge.get("findings_summary") or [])[:5]
    return {
        "nodes_discovered": [n.get("label") or n.get("id") for n in nodes],
        "connections_discovered": len(edges),
        "edges": [{"source": e.get("source"), "target": e.get("target"), "connection_type": e.get("connection_type"), "risk_score": e.get("risk_score")} for e in edges[:10]],
        "highest_risk_edge": {"source": max_edge.get("source"), "target": max_edge.get("target"), "risk_score": max_edge.get("risk_score")} if max_edge else None,
        "total_graph_risk_score": risk_graph.get("total_risk_score"),
        "findings_on_edge": edge_findings,
    }


def _build_pipeline_trace() -> list[str]:
    """Return analysis pipeline steps executed."""
    return [
        "Input normalization",
        "SaaS metadata extraction",
        "OAuth scope analysis",
        "Token misuse detection",
        "Credential exposure scan",
        "Data flow risk analysis",
        "Integration mapping",
        "AI governance detection",
        "Rule engine evaluation",
        "Risk score aggregation",
        "Compliance mapping",
        "Report generation",
    ]


def _build_attack_scenario(result: PipelineResult) -> dict[str, Any]:
    """Build Potential Attack Scenario from signals."""
    steps: list[str] = []
    o = result.saas_signals.oauth
    t = result.saas_signals.tokens
    c = result.saas_signals.credentials
    f = result.saas_signals.data_flow
    if c.exposed_credentials > 0 or (c.credential_scan_findings and len(c.credential_scan_findings) > 0):
        steps.append("Attacker discovers exposed API token or credential in integration configuration or logs.")
    if t.long_lived_tokens > 0 or t.rotation_disabled:
        steps.append("Token is long-lived and/or rotation is disabled, extending the window for abuse.")
    if t.shared_across_integrations:
        steps.append("Token is reused across integrations; compromise of one integration affects all connected systems.")
    if o.over_permissioned:
        steps.append("OAuth scopes are over-privileged; stolen token grants broad access to data and APIs.")
    if f.cross_platform_risk and f.sensitive_data_exposed:
        steps.append("Sensitive data flows cross-platform; attacker can exfiltrate PII or customer data via the destination system.")
    if not steps:
        steps.append("No high-confidence attack path inferred from current findings; review findings and scope for residual risk.")
    impact = "Unauthorized access to connected SaaS systems and potential exfiltration of sensitive data."
    if f.source_app and f.destination_app:
        impact = f"Unauthorized access to {f.source_app} and {f.destination_app}; potential data exfiltration and privilege escalation."
    return {"steps": steps, "impact": impact}


def _build_integration_visibility_summary(integration_map: IntegrationMap | None) -> dict[str, Any] | None:
    """Build integration visibility summary from integration map."""
    if not integration_map or (not integration_map.links and not integration_map.systems):
        return None
    return {
        "integration_id": integration_map.integration_id,
        "systems": integration_map.systems,
        "links_count": len(integration_map.links),
        "has_oauth": integration_map.has_oauth,
        "has_api": integration_map.has_api,
        "links": [link.model_dump() for link in integration_map.links[:20]],
    }


def _build_top_risky_connections(
    integration_map: IntegrationMap | None,
    risk_score: float,
    integration_id: str,
) -> list[dict[str, Any]]:
    """Build top risky connections list (for single scan: one or more links with score)."""
    if not integration_map or not integration_map.links:
        if integration_id and risk_score > 0:
            return [{"integration_id": integration_id, "risk_score": risk_score, "source": "", "target": ""}]
        return []
    return [
        {
            "source": link.source,
            "target": link.target,
            "risk_score": risk_score,
            "connection_type": link.link_type,
        }
        for link in integration_map.links[:10]
    ]


def _build_ai_data_flow_risks(metadata: dict[str, Any]) -> dict[str, Any] | None:
    """Build AI data flow risks section from pipeline metadata."""
    if not metadata.get("ai_risk_detected") and not metadata.get("enterprise_data_to_ai"):
        return None
    return {
        "ai_risk_detected": bool(metadata.get("ai_risk_detected")),
        "ai_findings_count": metadata.get("ai_findings_count", 0),
        "ai_risk_score": metadata.get("ai_risk_score", 0.0),
        "shadow_ai_detected": bool(metadata.get("shadow_ai_detected")),
        "enterprise_data_to_ai": bool(metadata.get("enterprise_data_to_ai")),
        "remediation_hint": (
            "Review AI-enabled integrations; restrict sensitive data to approved AI systems; "
            "inventory and document all AI data flows."
        ),
    }


def _build_remediation_recommendations(
    result: PipelineResult,
    compliance_mappings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build prioritized remediation with affected component, risk explanation, compliance framework."""
    recs: list[dict[str, Any]] = []
    seen: set[str] = set()

    for m in compliance_mappings:
        rem = (m.get("recommended_remediation") or "").strip()
        if rem and rem not in seen:
            seen.add(rem)
            finding_type = m.get("finding_type", "")
            if "oauth" in finding_type.lower() or "scope" in finding_type.lower():
                component, risk_expl = "OAuth configuration", "Over-permissioned scope increases blast radius if token is compromised."
            elif "token" in finding_type.lower():
                component, risk_expl = "Token lifecycle", "Long-lived or reused tokens extend exposure window."
            elif "credential" in finding_type.lower():
                component, risk_expl = "Credentials", "Exposed secrets enable unauthorized access."
            elif "data_flow" in finding_type.lower() or "cross_platform" in finding_type.lower():
                component, risk_expl = "Data flow", "Sensitive data crossing system boundaries may violate policy."
            else:
                component, risk_expl = "Integration configuration", "Finding indicates potential security or compliance gap."
            recs.append({
                "priority": "high" if (m.get("severity") or 3) >= 4 else "medium",
                "title": f"{m.get('framework', '')} {m.get('control_reference', '')}".strip() or "Remediation",
                "body": rem,
                "affected_component": component,
                "risk_explanation": risk_expl,
                "compliance_framework": m.get("framework", ""),
            })

    if result.saas_signals.oauth.over_permissioned and "least-privilege" not in str(seen).lower():
        recs.append({
            "priority": "high",
            "title": "Reduce OAuth scope over-permission",
            "body": "Apply least-privilege OAuth scopes; remove wildcard and admin scopes.",
            "affected_component": "OAuth configuration",
            "risk_explanation": "Over-permissioned scope increases blast radius if token is compromised.",
            "compliance_framework": "SOC2",
        })
    if result.saas_signals.data_flow.cross_platform_risk:
        recs.append({
            "priority": "high",
            "title": "Review cross-platform data exposure",
            "body": "Ensure data classification and DLP at integration boundaries.",
            "affected_component": "Data flow",
            "risk_explanation": "Sensitive data crossing system boundaries may violate policy.",
            "compliance_framework": "",
        })
    return recs[:15]


def build_report_from_pipeline(
    result: PipelineResult,
    rule_set: RuleSet,
    dataset_context: dict[str, Any] | None = None,
) -> ScanReport:
    max_sev, ceiling = severity_info(list(result.text_findings))
    score = result.combined_score
    meta = _pipeline_metadata(result)
    norm_meta = result.normalized.metadata

    # Integration map (from pipeline metadata)
    integration_map_raw = norm_meta.get("integration_map")
    integration_map: IntegrationMap | None = None
    if isinstance(integration_map_raw, dict):
        try:
            integration_map = IntegrationMap.model_validate(integration_map_raw)
        except Exception:
            integration_map = None
    elif hasattr(integration_map_raw, "model_dump"):
        integration_map = integration_map_raw

    # Risk graph
    risk_graph_dict: dict[str, Any] | None = None
    if integration_map:
        risk_graph = build_risk_graph(
            integration_map,
            risk_score=score,
            findings=result.text_findings,
            max_severity=max_sev,
        )
        risk_graph_dict = risk_graph.model_dump()

    # Compliance mapping
    compliance_result = map_findings_to_frameworks(result.text_findings, include_ai_context=True)
    compliance_mapping = [m.model_dump() for m in compliance_result.mappings]

    # Remediation recommendations (with component, risk_explanation, compliance_framework)
    remediation_recommendations = _build_remediation_recommendations(result, compliance_mapping)

    return ScanReport(
        risk_score=score,
        risk_level=risk_level_from_score(score),
        max_severity_found=max_sev,
        severity_ceiling_applied=ceiling,
        risk_summary=result.risk_summary,
        oauth_analysis=result.saas_signals.oauth,
        token_analysis=result.saas_signals.tokens,
        credential_exposure=result.saas_signals.credentials,
        data_flow_risk=result.saas_signals.data_flow,
        findings=list(result.text_findings),
        matched_rules=[r for r in result.matched_rules if r.matched],
        metadata=meta,
        executive_summary=_build_executive_summary(result, max_sev),
        integration_visibility_summary=_build_integration_visibility_summary(integration_map),
        top_risky_connections=_build_top_risky_connections(integration_map, score, result.normalized.target),
        ai_data_flow_risks=_build_ai_data_flow_risks(norm_meta),
        compliance_mapping=compliance_mapping,
        remediation_recommendations=remediation_recommendations,
        risk_graph=risk_graph_dict,
        analyzed_input_overview=_build_analyzed_input_overview(result),
        integration_metadata=_build_integration_metadata(result),
        detection_signals=_build_detection_signals(result),
        analyzer_breakdown=_build_analyzer_breakdown(result),
        risk_graph_summary=_build_risk_graph_summary(risk_graph_dict),
        dataset_context=dataset_context,
        pipeline_trace=_build_pipeline_trace(),
        attack_scenario=_build_attack_scenario(result),
    )


def build_report_from_scan_input(response: ScanInputResponse, rule_set: RuleSet) -> ScanReport:
    findings: list[TextFinding] = list(response.text_findings)
    meta: dict[str, Any] = {
        "target": response.target,
        "content_length": response.content_length,
        "total_score": response.total_score,
        "text_scan_score": response.text_scan_score,
        "passed_count": response.passed_count,
        "failed_count": response.failed_count,
        "text_matched_count": response.text_matched_count,
    }
    risk = cvss_combined_score(
        response.total_score, findings, rule_set.text_scan_rules
    )
    max_sev, ceiling = severity_info(findings)
    return ScanReport(
        risk_score=risk,
        risk_level=risk_level_from_score(risk),
        max_severity_found=max_sev,
        severity_ceiling_applied=ceiling,
        findings=findings,
        matched_rules=[r for r in response.matched_rules if r.matched],
        metadata=meta,
    )
