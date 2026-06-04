"""Composite risk scoring and data-flow analysis.

Uses the shared scoring engine in app.core.risk_engine for composite
risk (weights: OAuth 30%, Token Misuse 25%, Credential 35%, Data Flow 10%).
This module adds: analyze_data_flow, cvss_combined_score, severity_info.
"""

from __future__ import annotations

import re
from typing import Any

from app.core.logging import get_logger
from app.core.risk_engine import (  # noqa: F401  (re-exported for callers)
    compute_composite_score,
    risk_level_from_score,
)
from app.models.scan_models import (
    DataFlowRisk,
    TextFinding,
    TextScanRule,
)

logger = get_logger(__name__)

_SENSITIVE_DATA_TYPES = {
    "pii", "financial", "credentials", "customer_data",
    "secrets", "tokens", "phi", "health",
}

_SEV_BASE: dict[int, float] = {5: 80.0, 4: 60.0, 3: 40.0, 2: 20.0, 1: 10.0}


def _iter_nodes(value: Any):
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from _iter_nodes(nested)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_nodes(item)


def analyze_data_flow(payload: Any) -> DataFlowRisk:
    """Detect cross-platform data flow risk from integration payload."""
    source = None
    destination = None
    data_types: set[str] = set()

    for node in _iter_nodes(payload):
        if not isinstance(node, dict):
            continue
        for key, value in node.items():
            lowered = key.lower()
            if lowered in {"source", "source_app", "from_app"} and isinstance(value, str):
                source = value.strip().lower()
            if lowered in {"destination", "destination_app", "to_app", "target_app"} and isinstance(value, str):
                destination = value.strip().lower()
            if lowered in {"data_types", "shared_data_types", "data_classification"}:
                if isinstance(value, str):
                    data_types.update(s.strip().lower() for s in re.split(r"[\s,]+", value.strip()) if s)
                elif isinstance(value, list):
                    data_types.update(str(s).strip().lower() for s in value)

    cross_platform = bool(source and destination and source != destination)
    sensitive = bool(data_types & _SENSITIVE_DATA_TYPES)

    flow_risk_score = 0.0
    if cross_platform and sensitive:
        flow_risk_score = 60.0
        flow_risk_score += min(len(data_types & _SENSITIVE_DATA_TYPES) * 10.0, 30.0)
    elif cross_platform:
        flow_risk_score = 20.0
    elif sensitive:
        flow_risk_score = 30.0

    return DataFlowRisk(
        source_app=source,
        destination_app=destination,
        data_types=sorted(data_types),
        sensitive_data_exposed=sensitive,
        cross_platform_risk=cross_platform and sensitive,
        flow_risk_score=round(min(100.0, flow_risk_score), 2),
    )


def cvss_combined_score(
    context_score: float,
    findings: list[TextFinding],
    text_scan_rules: list[TextScanRule],
) -> float:
    """CVSS-inspired combined score for the text-scan + context engines.

    Kept for backward compatibility with the existing pipeline.
    """
    matched_counts: dict[str, int] = {}
    for f in findings:
        matched_counts[f.rule_id] = matched_counts.get(f.rule_id, 0) + 1

    if not matched_counts:
        return round(min(100.0, context_score * 0.5), 2)

    rule_map = {r.id: r for r in text_scan_rules}
    severities = [rule_map[rid].severity for rid in matched_counts if rid in rule_map]
    max_sev = max(severities) if severities else 1

    base = _SEV_BASE.get(max_sev, 10.0)
    breadth_bonus = min((len(matched_counts) - 1) * 5.0, 15.0)
    repeat_bonus = min(float(sum(max(0, c - 1) for c in matched_counts.values())), 5.0)

    text_component = min(100.0, base + breadth_bonus + repeat_bonus)
    context_multiplier = 1.0 + (context_score / 100.0) * 0.25
    raw = min(100.0, text_component * context_multiplier)

    if max_sev >= 5 and raw < 80.0:
        raw = 80.0
    elif max_sev >= 4 and raw < 60.0:
        raw = 60.0

    return round(raw, 2)


def severity_info(findings: list[TextFinding]) -> tuple[int, bool]:
    if not findings:
        return 0, False
    max_sev = max(f.severity for f in findings)
    return max_sev, max_sev >= 4
