"""OAuth scope parser and risk assessor.

Parses OAuth scopes from SaaS integration artifacts (JSON/YAML configs),
evaluates each scope against the configurable policy file
(``policies/oauth_scopes.yaml``), and produces an :class:`OAuthAnalysis`
with per-scope risk ratings and an aggregate over-permission verdict.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from app.core.logging import get_logger
from app.models.scan_models import OAuthAnalysis, OAuthScopeRisk

logger = get_logger(__name__)

_POLICY_PATH = Path(__file__).resolve().parent.parent / "policies" / "oauth_scopes.yaml"

_SCOPE_KEYS = {"scope", "scopes", "oauth_scope", "oauth_scopes", "permissions"}

_policy_cache: dict | None = None


def _load_policy() -> dict:
    global _policy_cache
    if _policy_cache is not None:
        return _policy_cache
    if not _POLICY_PATH.exists():
        logger.warning("OAuth scopes policy not found at %s — using defaults", _POLICY_PATH)
        _policy_cache = {}
        return _policy_cache
    with _POLICY_PATH.open("r", encoding="utf-8") as f:
        _policy_cache = yaml.safe_load(f) or {}
    return _policy_cache


def _iter_nodes(value: Any):
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from _iter_nodes(nested)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_nodes(item)


def _split_scope_string(raw: str) -> list[str]:
    return [c for c in re.split(r"[\s,]+", raw.strip()) if c]


def _collect_scope_values(value: Any, scopes: list[str]) -> None:
    """Append scope strings from a value that is a string or list."""
    if isinstance(value, str):
        scopes.extend(_split_scope_string(value))
    elif isinstance(value, list):
        scopes.extend(str(v) for v in value if isinstance(v, (str, int, float)))


def _extract_slack_manifest_scopes(payload: Any) -> list[str]:
    """Extract scopes from Slack app manifest ``oauth_config.scopes``."""
    scopes: list[str] = []
    for node in _iter_nodes(payload):
        if not isinstance(node, dict):
            continue
        oauth_config = node.get("oauth_config")
        if not isinstance(oauth_config, dict):
            continue
        scope_block = oauth_config.get("scopes")
        if isinstance(scope_block, dict):
            for channel in ("bot", "user"):
                _collect_scope_values(scope_block.get(channel), scopes)
        else:
            _collect_scope_values(scope_block, scopes)
        redirect_urls = oauth_config.get("redirect_urls", [])
        if isinstance(redirect_urls, list):
            for url in redirect_urls:
                if isinstance(url, str) and re.search(
                    r'(?i)(?:token|secret|key)=[^\s&]{6,}', url
                ):
                    logger.warning("Slack manifest redirect_url contains embedded secret")
    return scopes


def extract_scopes(payload: Any) -> list[str]:
    """Walk a nested payload and collect all OAuth scope values.

    Handles generic scope keys, Slack manifest ``oauth_config.scopes``,
    and Atlassian Connect ``scopes`` arrays.
    """
    scopes: list[str] = []

    scopes.extend(_extract_slack_manifest_scopes(payload))

    for node in _iter_nodes(payload):
        if not isinstance(node, dict):
            continue
        for key, value in node.items():
            if key.lower() not in _SCOPE_KEYS:
                continue
            _collect_scope_values(value, scopes)

    unique: list[str] = []
    seen: set[str] = set()
    for scope in scopes:
        lowered = scope.strip().lower()
        if lowered and lowered not in seen:
            seen.add(lowered)
            unique.append(lowered)
    return unique


def _is_wildcard(scope: str, wildcard_patterns: list[str]) -> bool:
    for pattern in wildcard_patterns:
        if pattern in scope:
            return True
    return False


def _risk_level_from_severity(sev: int) -> str:
    if sev >= 5:
        return "CRITICAL"
    if sev >= 4:
        return "HIGH"
    if sev >= 3:
        return "MEDIUM"
    if sev >= 2:
        return "LOW"
    return "MINIMAL"


def analyze_scopes(payload: Any) -> OAuthAnalysis:
    """Analyze OAuth scopes from a SaaS integration payload.

    Loads the policy from ``policies/oauth_scopes.yaml`` and evaluates
    each extracted scope for risk level.
    """
    policy = _load_policy()
    scopes = extract_scopes(payload)

    if not scopes:
        return OAuthAnalysis()

    high_risk_defs = policy.get("high_risk_scopes", [])
    wildcard_patterns = policy.get("wildcard_patterns", ["*", ".*", ".all", "full_access"])
    thresholds = policy.get("over_permission_thresholds", {})
    safe_scope_list = {s.lower() for s in policy.get("safe_scopes", [])}

    wildcard_trigger = thresholds.get("wildcard_scope_trigger", 1)
    high_risk_trigger = thresholds.get("high_risk_scope_trigger", 2)
    total_trigger = thresholds.get("total_scope_trigger", 8)

    high_risk_scopes: list[OAuthScopeRisk] = []
    wildcard_scopes: list[str] = []
    safe_scopes: list[str] = []

    for scope in scopes:
        is_wc = _is_wildcard(scope, wildcard_patterns)
        if is_wc:
            wildcard_scopes.append(scope)

        if scope in safe_scope_list:
            safe_scopes.append(scope)
            continue

        matched_risk = None
        for rule in high_risk_defs:
            if rule.get("pattern", "").lower() in scope:
                matched_risk = rule
                break

        if matched_risk or is_wc:
            sev = matched_risk.get("severity", 4) if matched_risk else 4
            desc = matched_risk.get("description", "Wildcard scope grants broad access") if matched_risk else "Wildcard scope grants broad access"
            high_risk_scopes.append(OAuthScopeRisk(
                scope=scope,
                risk_level=_risk_level_from_severity(sev),
                severity=sev,
                description=desc,
                is_wildcard=is_wc,
            ))

    over_permissioned = bool(
        len(wildcard_scopes) >= wildcard_trigger
        or len(high_risk_scopes) >= high_risk_trigger
        or len(scopes) >= total_trigger
    )

    # Scope risk score: weighted combination of high-risk severity
    if not high_risk_scopes:
        scope_risk_score = 0.0
    else:
        max_sev = max(s.severity for s in high_risk_scopes)
        breadth = min(len(high_risk_scopes) * 8.0, 30.0)
        base = {5: 60.0, 4: 45.0, 3: 30.0, 2: 15.0, 1: 5.0}.get(max_sev, 10.0)
        scope_risk_score = min(100.0, base + breadth + (10.0 if over_permissioned else 0.0))

    return OAuthAnalysis(
        total_scopes=len(scopes),
        scopes=scopes,
        high_risk_scopes=high_risk_scopes,
        wildcard_scopes=wildcard_scopes,
        safe_scopes=safe_scopes,
        over_permissioned=over_permissioned,
        scope_risk_score=round(scope_risk_score, 2),
    )


def get_oauth_policy() -> dict:
    """Return the parsed OAuth scope policy (for API/docs). Same structure as oauth_scopes.yaml."""
    return _load_policy()


def clear_policy_cache() -> None:
    global _policy_cache
    _policy_cache = None
