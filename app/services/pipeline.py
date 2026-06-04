"""SaaSShadow scan pipeline.

Orchestrates the full integration analysis flow:

  1. Normalize  — canonical text from raw input (text / JSON / bytes)
  2. Detect     — content-type, language, quick-hit signal flags
  3. Analyze    — OAuth scopes, API tokens, credentials, data flow
  4. Rule Engine — context + text-scan rules with CVSS-style scoring
  5. Report     — assemble exportable JSON report
"""

from __future__ import annotations

import json
from typing import Any

from app.core.logging import get_logger
from app.core.risk_engine import compute_risk_summary
from app.models.scan_models import (
    DetectionFlags,
    NormalizedInput,
    PipelineRequest,
    PipelineResult,
    RuleSet,
    SaaSSignalSummary,
)
from app.analysis.api_detector import detect as detect_api_surface
from app.analysis.integration_mapper import map_integrations
from app.analyzers.ai_integrations import detect_ai_integrations
from app.analyzers.credential_exposure import scan_credentials
from app.services.arm_template_analyzer import analyze_arm_template
from app.services.credential_detector import detect_credential_exposure
from app.services.detection import detect
from app.services.entra_manifest_parser import analyze_entra_manifest
from app.services.normalizer import normalize, normalize_json, normalize_text
from app.services.oauth_parser import analyze_scopes
from app.services.report_generator import build_report_from_pipeline
from app.services.risk_engine import (
    analyze_data_flow,
    compute_composite_score,
    cvss_combined_score,
)
from app.services.rule_engine import evaluate, scan_text, text_scan_rule_matches
from app.services.rules_loader import load_rules
from app.services.token_analyzer import analyze_tokens
from app.services.workflow_graph_analyzer import analyze_workflow

logger = get_logger(__name__)


def _stage_normalize_from_request(req: PipelineRequest) -> NormalizedInput:
    """Stage 1 — build canonical NormalizedInput from the request."""
    metadata = dict(req.metadata)
    if req.json_data is not None and req.text is not None:
        norm = normalize_json(req.json_data, target=req.target, metadata=metadata)
        norm = norm.model_copy(update={"content": req.text, "input_kind": "text"})
        return norm
    if req.json_data is not None:
        return normalize_json(req.json_data, target=req.target, metadata=metadata)
    return normalize_text(req.text or "", target=req.target, metadata=metadata)


def _stage_detect(normalized: NormalizedInput) -> DetectionFlags:
    """Stage 2 — detection utilities."""
    return detect(normalized)


def _resolve_payload(normalized: NormalizedInput) -> Any:
    """Recover the structured payload for SaaS-specific analyzers."""
    if normalized.input_kind == "json":
        try:
            return json.loads(normalized.content)
        except (TypeError, ValueError):
            pass
    return normalized.metadata


def _stage_saas_analysis(
    normalized: NormalizedInput,
    payload: Any,
    rule_set: RuleSet,
) -> tuple[SaaSSignalSummary, PipelineResult]:
    """Stage 3+4 — SaaS signal extraction + rule engines."""
    # Entra manifest gets priority — if detected, its OAuth analysis
    # replaces the generic one for higher fidelity on GUID-based scopes.
    entra_oauth = analyze_entra_manifest(payload)
    oauth = entra_oauth if entra_oauth is not None else analyze_scopes(payload)

    tokens = analyze_tokens(normalized.content, payload, normalized.metadata)
    data_flow = analyze_data_flow(payload)

    # ARM template / connector wiring analysis
    arm_result = analyze_arm_template(normalized.content, payload)

    # Workflow graph analysis (n8n, Node-RED, Logic Apps, Step Functions)
    workflow_result = analyze_workflow(normalized.content, payload)

    # If the workflow analyzer inferred services but data_flow has no
    # source/destination, backfill from the workflow graph.
    if workflow_result.inferred_services and not data_flow.source_app:
        services = sorted(set(workflow_result.inferred_services))
        if len(services) >= 2:
            data_flow = data_flow.model_copy(update={
                "source_app": services[0],
                "destination_app": services[1],
                "cross_platform_risk": data_flow.cross_platform_risk or True,
            })
        elif len(services) == 1:
            data_flow = data_flow.model_copy(update={"source_app": services[0]})

    # SaaS integration visibility — structured map for reporting and risk graph
    integration_map = map_integrations(
        payload,
        integration_id=normalized.target,
        existing_source=data_flow.source_app,
        existing_destination=data_flow.destination_app,
    )

    # API + webhook detection — populates IntegrationMap.raw_metadata.api_detection
    api_detection = detect_api_surface(payload, normalized.content)
    api_detection_dict = api_detection.to_metadata_dict()
    if integration_map.raw_metadata is None:
        integration_map = integration_map.model_copy(update={"raw_metadata": {}})
    new_raw = dict(integration_map.raw_metadata or {})
    new_raw["api_detection"] = api_detection_dict
    integration_map = integration_map.model_copy(update={"raw_metadata": new_raw})

    # Promote link types based on API detection (e.g. webhook beats unknown)
    if api_detection.has_webhook and integration_map.links:
        integration_map = integration_map.model_copy(
            update={
                "links": [
                    link.model_copy(update={"link_type": "webhook"})
                    if link.link_type == "unknown" and api_detection.has_webhook
                    else link
                    for link in integration_map.links
                ]
            }
        )
    integration_map = integration_map.model_copy(
        update={
            "has_api": integration_map.has_api or api_detection.has_rest or api_detection.has_graphql or api_detection.has_grpc,
        }
    )

    normalized = normalized.model_copy(
        update={
            "metadata": {
                **normalized.metadata,
                "integration_map": integration_map.model_dump(),
                "api_detection": api_detection_dict,
            }
        }
    )

    # Context dict for pattern-rule engine — every field here is
    # available to context rules via ``field`` references in YAML.
    context: dict[str, Any] = dict(normalized.metadata)
    context.setdefault("target", normalized.target)
    context.setdefault("text", normalized.content)
    # OAuth dimension
    context.setdefault("oauth_scope_count", oauth.total_scopes)
    context.setdefault("oauth_high_risk_scope_count", len(oauth.high_risk_scopes))
    context.setdefault("oauth_wildcard_scope_count", len(oauth.wildcard_scopes))
    context.setdefault("oauth_over_permission", oauth.over_permissioned)
    context.setdefault("oauth_scope_risk_score", oauth.scope_risk_score)
    # Token dimension
    context.setdefault("token_misuse_count", len(tokens.misuse_patterns))
    context.setdefault("token_misuse_patterns", tokens.misuse_patterns)
    context.setdefault("tokens_found", tokens.tokens_found)
    context.setdefault("tokens_in_urls", tokens.tokens_in_urls)
    context.setdefault("long_lived_tokens", tokens.long_lived_tokens)
    context.setdefault("weak_tokens", tokens.weak_tokens)
    context.setdefault("token_rotation_disabled", tokens.rotation_disabled)
    context.setdefault("token_shared_across_integrations", tokens.shared_across_integrations)
    # Data flow dimension
    context.setdefault("cross_platform_data_exposure", data_flow.cross_platform_risk)
    context.setdefault("sensitive_data_exposed", data_flow.sensitive_data_exposed)
    context.setdefault("source_app", data_flow.source_app or "")
    context.setdefault("destination_app", data_flow.destination_app or "")
    # ARM template dimension
    context.setdefault("arm_is_template", arm_result.is_arm_template)
    context.setdefault("arm_insecure_params", len(arm_result.insecure_params))
    context.setdefault("arm_inline_credentials", len(arm_result.inline_credentials))
    context.setdefault("arm_risk_score", arm_result.arm_risk_score)
    # Workflow dimension
    context.setdefault("workflow_platform", workflow_result.platform or "")
    context.setdefault("workflow_credential_refs", len(workflow_result.credential_refs))
    context.setdefault("workflow_findings_count", len(workflow_result.findings))
    context.setdefault("workflow_risk_score", workflow_result.workflow_risk_score)
    # Integration map for rules and reporting
    context.setdefault("integration_map", integration_map.model_dump())

    ctx_result = evaluate(context, rule_set)
    txt_result = scan_text(normalized.content, rule_set)

    # Credential exposure scanner (regex + entropy) — merge with text-scan findings
    integration_context = {
        "target": normalized.target,
        "source_app": data_flow.source_app,
        "destination_app": data_flow.destination_app,
    }
    credential_scan_result = scan_credentials(
        normalized.content,
        location=normalized.target or "content",
        integration_context=integration_context,
    )
    txt_result.findings.extend(credential_scan_result.to_text_findings())
    if credential_scan_result.findings:
        txt_result.matched_count = len(txt_result.findings)
        # Recompute text score to include scanner findings (simplified: add weight per new finding)
        txt_result.total_score = round(
            min(100.0, txt_result.total_score + min(len(credential_scan_result.findings) * 5.0, 30.0)),
            2,
        )

    # AI + SaaS data flow governance — merge findings into text findings and context
    ai_result = detect_ai_integrations(
        payload,
        normalized.content,
        integration_id=normalized.target,
        source_app=data_flow.source_app,
        destination_app=data_flow.destination_app,
        content_location=normalized.target or "content",
    )
    txt_result.findings.extend(ai_result.to_text_findings())
    if ai_result.findings:
        txt_result.matched_count = len(txt_result.findings)
        txt_result.total_score = round(
            min(100.0, txt_result.total_score + min(len(ai_result.findings) * 6.0, 25.0)),
            2,
        )
    context.setdefault("ai_risk_detected", bool(ai_result.findings))
    context.setdefault("ai_findings_count", len(ai_result.findings))
    context.setdefault("ai_risk_score", ai_result.ai_risk_score)
    context.setdefault("shadow_ai_detected", ai_result.shadow_ai_detected)
    context.setdefault("enterprise_data_to_ai", ai_result.enterprise_data_to_ai)
    normalized = normalized.model_copy(
        update={
            "metadata": {
                **normalized.metadata,
                "ai_risk_detected": bool(ai_result.findings),
                "ai_findings_count": len(ai_result.findings),
                "ai_risk_score": ai_result.ai_risk_score,
                "shadow_ai_detected": ai_result.shadow_ai_detected,
                "enterprise_data_to_ai": ai_result.enterprise_data_to_ai,
            }
        }
    )

    # Credential exposure from text-scan + credential scanner findings
    credentials = detect_credential_exposure(txt_result)
    credentials = credentials.model_copy(
        update={
            "credential_scan_findings": credential_scan_result.findings,
            "credential_risk_score": round(
                max(credentials.credential_risk_score, credential_scan_result.credential_risk_score),
                2,
            )
            if credential_scan_result.findings
            else credentials.credential_risk_score,
        }
    )

    signals = SaaSSignalSummary(
        oauth=oauth,
        tokens=tokens,
        credentials=credentials,
        data_flow=data_flow,
    )

    combined = cvss_combined_score(
        ctx_result.total_score, txt_result.findings, rule_set.text_scan_rules
    )

    # Factor in the SaaS-specific dimension scores
    composite = compute_composite_score(signals)

    # Blend in ARM, workflow, and AI risk as supplementary signals
    supplementary = max(
        arm_result.arm_risk_score,
        workflow_result.workflow_risk_score,
        ai_result.ai_risk_score,
    )
    if supplementary > 0:
        composite = round(min(100.0, composite * 0.82 + supplementary * 0.18), 2)

    final_score = round(max(combined, composite), 2)

    result = PipelineResult(
        normalized=normalized,
        detection=DetectionFlags(),
        matched_rules=[
            r for r in ctx_result.matched_rules + text_scan_rule_matches(txt_result, rule_set)
            if r.matched
        ],
        context_score=ctx_result.total_score,
        passed_count=ctx_result.passed_count,
        failed_count=ctx_result.failed_count,
        text_findings=txt_result.findings,
        text_scan_score=txt_result.total_score,
        text_matched_count=txt_result.matched_count,
        saas_signals=signals,
        combined_score=final_score,
        risk_summary=compute_risk_summary(
            normalized.target,
            signals,
            final_score,
            txt_result.findings,
        ),
    )
    return signals, result


# ── Public pipeline functions ─────────────────────────────────────────────────


def run_pipeline(
    req: PipelineRequest,
    rule_set: RuleSet | None = None,
) -> PipelineResult:
    """Execute the full SaaSShadow analysis pipeline.

    Flow: Normalize → Detect → OAuth/Token/Credential/DataFlow analysis
    → Context + Text-scan rule engines → Composite scoring → Report.
    """
    if rule_set is None:
        rule_set = load_rules()

    logger.info("Pipeline start: target=%s", req.target)

    normalized = _stage_normalize_from_request(req)
    logger.debug("Normalized: kind=%s len=%d", normalized.input_kind, normalized.content_length)

    detection = _stage_detect(normalized)
    logger.debug("Detection: type=%s flags=%s", detection.content_type, detection.flags)

    payload = _resolve_payload(normalized)
    _signals, result = _stage_saas_analysis(normalized, payload, rule_set)

    result = result.model_copy(update={"detection": detection})
    result = result.model_copy(update={"report": build_report_from_pipeline(result, rule_set)})

    logger.info(
        "Pipeline complete: target=%s combined=%.2f oauth=%.2f tokens=%.2f creds=%.2f flow=%.2f",
        req.target,
        result.combined_score,
        _signals.oauth.scope_risk_score,
        _signals.tokens.token_risk_score,
        _signals.credentials.credential_risk_score,
        _signals.data_flow.flow_risk_score,
    )
    return result


def run_pipeline_raw(
    raw: str | bytes | dict[str, Any],
    target: str = "raw-input",
    metadata: dict[str, Any] | None = None,
    filename: str | None = None,
    rule_set: RuleSet | None = None,
) -> PipelineResult:
    """Convenience wrapper for programmatic callers and tests."""
    normalized = normalize(raw, target=target, metadata=metadata, filename=filename)
    if rule_set is None:
        rule_set = load_rules()

    detection = _stage_detect(normalized)
    payload = _resolve_payload(normalized)
    _signals, result = _stage_saas_analysis(normalized, payload, rule_set)

    result = result.model_copy(update={"detection": detection})
    result = result.model_copy(update={"report": build_report_from_pipeline(result, rule_set)})
    return result
