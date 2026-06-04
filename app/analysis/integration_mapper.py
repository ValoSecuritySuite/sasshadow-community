"""SaaS-to-SaaS integration visibility layer.

Parses scan inputs and integration metadata to:
- Identify connected SaaS systems
- Extract source/target relationships
- Detect API / OAuth-based links
- Capture cross-platform data flow direction

Output is structured for reuse by reporting and graph generation.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.logging import get_logger

logger = get_logger(__name__)

# ── Output models ─────────────────────────────────────────────────────────────

LinkType = Literal["oauth", "api", "webhook", "connector", "workflow", "unknown"]
FlowDirection = Literal["inbound", "outbound", "bidirectional", "unknown"]


class IntegrationLink(BaseModel):
    """A single connection between two systems."""

    source: str = Field(description="Source system or app identifier")
    target: str = Field(description="Target system or app identifier")
    link_type: LinkType = Field(default="unknown", description="OAuth, API, webhook, connector, workflow")
    direction: FlowDirection = Field(default="unknown", description="Data flow direction")
    data_types: list[str] = Field(default_factory=list, description="Data types flowing (e.g. pii, customer_data)")
    evidence: list[str] = Field(default_factory=list, description="Short evidence strings (e.g. scope names, endpoint keys)")


class IntegrationMap(BaseModel):
    """Structured integration mapping for a scan or batch.

    Reusable by reporting and enterprise risk graph generation.
    """

    integration_id: str = Field(default="", description="Scan target or integration identifier")
    links: list[IntegrationLink] = Field(default_factory=list, description="Discovered source→target links")
    systems: list[str] = Field(default_factory=list, description="Unique system/app names involved")
    has_oauth: bool = Field(default=False, description="At least one OAuth-based link detected")
    has_api: bool = Field(default=False, description="At least one API/key-based link detected")
    raw_metadata: dict[str, Any] = Field(default_factory=dict, description="Optional extra context for graph")


def _iter_nodes(value: Any):
    """Recursively yield dict nodes from a payload."""
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from _iter_nodes(nested)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_nodes(item)


def _normalize_system_name(name: str) -> str:
    """Lowercase, strip, and collapse whitespace for consistent node IDs."""
    if not name or not isinstance(name, str):
        return ""
    return " ".join(name.strip().lower().split())


def _infer_link_type(payload: Any, node: dict[str, Any]) -> LinkType:
    """Infer link type from payload and current node."""
    keys_lower = {k.lower() for k in node.keys()}
    if keys_lower & {"scope", "scopes", "oauth_scope", "oauth_scopes", "permissions"}:
        return "oauth"
    if keys_lower & {"access_token", "refresh_token", "bearer"}:
        return "oauth"
    if keys_lower & {"api_key", "apikey", "x-api-key", "api_endpoint"}:
        return "api"
    if keys_lower & {"webhook_url", "webhook", "callback_url", "callback"}:
        return "webhook"
    if keys_lower & {"connector", "connector_id", "connector_name"}:
        return "connector"
    if keys_lower & {"workflow", "trigger", "action", "steps"}:
        return "workflow"
    # Check payload-level hints
    for n in _iter_nodes(payload):
        if not isinstance(n, dict):
            continue
        k = (n.get("type") or n.get("kind") or "").lower()
        if "oauth" in k or "oauth2" in k:
            return "oauth"
        if "api" in k or "rest" in k:
            return "api"
        if "webhook" in k:
            return "webhook"
    return "unknown"


def _infer_direction(
    source: str,
    target: str,
    node: dict[str, Any],
    payload: Any,
) -> FlowDirection:
    """Infer data flow direction from context where possible."""
    keys_lower = {k.lower() for k in node.keys()}
    if "inbound" in str(node.values()).lower() or "ingest" in str(node.values()).lower():
        return "inbound"
    if "outbound" in str(node.values()).lower() or "export" in str(node.values()).lower():
        return "outbound"
    # Default: source → target is outbound from source
    if source and target:
        return "outbound"
    return "unknown"


def _collect_evidence(node: dict[str, Any], link_type: LinkType) -> list[str]:
    """Collect short evidence strings for the link."""
    evidence: list[str] = []
    for key, value in node.items():
        key_lower = key.lower()
        if link_type == "oauth" and key_lower in {"scope", "scopes", "oauth_scope", "oauth_scopes"}:
            if isinstance(value, list):
                evidence.extend(str(s) for s in value[:5])
            elif isinstance(value, str):
                parts = [s.strip() for s in re.split(r"[\s,]+", value.strip()) if s]
                evidence.extend(parts[:5])
        if key_lower in {"api_endpoint", "webhook_url", "callback_url"} and isinstance(value, str):
            evidence.append(value.strip()[:80])
    return evidence[:10]


def map_integrations(
    payload: Any,
    integration_id: str = "",
    *,
    existing_source: str | None = None,
    existing_destination: str | None = None,
) -> IntegrationMap:
    """Parse scan input and integration metadata into a structured integration map.

    Args:
        payload: Structured integration JSON or dict (e.g. from NormalizedInput.metadata
                 or resolved json_data).
        integration_id: Optional scan target identifier (e.g. from PipelineRequest.target).
        existing_source: Optional precomputed source_app (e.g. from data flow analyzer).
        existing_destination: Optional precomputed destination_app.

    Returns:
        IntegrationMap with links, systems, OAuth/API flags, and raw_metadata for
        reporting and graph generation.
    """
    result = IntegrationMap(integration_id=integration_id or "unknown")
    if payload is None:
        return result

    source_candidates: set[str] = set()
    dest_candidates: set[str] = set()
    data_types: set[str] = set()
    link_type_seen: set[LinkType] = set()
    evidence_by_pair: dict[tuple[str, str], list[str]] = {}

    # Normalize from existing data flow if provided
    if existing_source:
        source_candidates.add(_normalize_system_name(existing_source))
    if existing_destination:
        dest_candidates.add(_normalize_system_name(existing_destination))

    for node in _iter_nodes(payload):
        if not isinstance(node, dict):
            continue
        for key, value in node.items():
            lowered = key.lower()
            if lowered in {"source", "source_app", "from_app", "origin"} and isinstance(value, str):
                source_candidates.add(_normalize_system_name(value))
            if lowered in {"destination", "destination_app", "to_app", "target_app", "target"} and isinstance(value, str):
                dest_candidates.add(_normalize_system_name(value))
            if lowered in {"data_types", "shared_data_types", "data_classification", "data_flow"}:
                if isinstance(value, str):
                    data_types.update(
                        s.strip().lower()
                        for s in re.split(r"[\s,]+", value.strip())
                        if s
                    )
                elif isinstance(value, list):
                    data_types.update(str(s).strip().lower() for s in value)

    # Infer from integration_id pattern "source_to_dest" or "source-dest"
    if integration_id and not (source_candidates or dest_candidates):
        for sep in ("_to_", "_", "-"):
            if sep in integration_id:
                parts = re.split(r"_to_|_|-", integration_id, 2)
                if len(parts) >= 2:
                    source_candidates.add(_normalize_system_name(parts[0]))
                    dest_candidates.add(_normalize_system_name(parts[1]))
                break

    # Build unique systems list
    all_systems = source_candidates | dest_candidates
    result.systems = sorted(all_systems)

    # Build one or more links
    sources = sorted(source_candidates) if source_candidates else list(all_systems)
    dests = sorted(dest_candidates) if dest_candidates else list(all_systems)

    if not sources and not dests:
        result.raw_metadata = _payload_metadata_snapshot(payload)
        return result

    # Infer link type and direction from payload once
    link_type: LinkType = "unknown"
    direction: FlowDirection = "outbound"
    evidence: list[str] = []
    for node in _iter_nodes(payload):
        if not isinstance(node, dict):
            continue
        link_type = _infer_link_type(payload, node)
        direction = _infer_direction(
            next(iter(sources), ""),
            next(iter(dests), ""),
            node,
            payload,
        )
        evidence = _collect_evidence(node, link_type)
        if evidence or link_type != "unknown":
            break

    # Build links: source -> destination pairs
    if len(sources) >= 1 and len(dests) >= 1:
        for src in sources:
            for tgt in dests:
                if src == tgt:
                    continue
                link_type_seen.add(link_type)
                result.links.append(
                    IntegrationLink(
                        source=src,
                        target=tgt,
                        link_type=link_type,
                        direction=direction,
                        data_types=sorted(data_types),
                        evidence=evidence[:10],
                    )
                )
    else:
        # Single system or only one side known
        for sys in result.systems:
            link_type_seen.add(link_type)
            result.links.append(
                IntegrationLink(
                    source=sys,
                    target="",
                    link_type=link_type,
                    direction="unknown",
                    data_types=sorted(data_types),
                    evidence=evidence[:10],
                )
            )

    result.has_oauth = "oauth" in link_type_seen
    result.has_api = "api" in link_type_seen
    result.raw_metadata = _payload_metadata_snapshot(payload)

    return result


def _payload_metadata_snapshot(payload: Any) -> dict[str, Any]:
    """Produce a small metadata snapshot for graph context (no secrets)."""
    out: dict[str, Any] = {}
    if not isinstance(payload, dict):
        return out
    safe_keys = {"source_app", "destination_app", "source", "destination", "data_types", "type", "kind"}
    for key, value in payload.items():
        if key.lower() in safe_keys and value is not None:
            if isinstance(value, (str, int, float, bool)):
                out[key] = value
            elif isinstance(value, list) and all(isinstance(x, (str, int, float, bool)) for x in value[:20]):
                out[key] = value[:20]
    return out
