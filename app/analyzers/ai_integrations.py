"""AI + SaaS data flow governance detection.

Detects patterns where AI systems or copilots connect to SaaS tools or
receive enterprise data. Flags risky data routing, shadow AI usage, and
unapproved AI-related integrations. Findings integrate with the shared
risk engine via text findings and context keys.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger
from app.models.scan_models import RiskLevel, TextFinding

logger = get_logger(__name__)

# Known AI / LLM / copilot provider and product identifiers (lowercase)
_AI_SYSTEMS = frozenset({
    "openai", "chatgpt", "gpt-4", "gpt-3", "davinci", "claude", "anthropic",
    "copilot", "github copilot", "microsoft copilot", "bing chat",
    "bard", "gemini", "google ai", "vertex ai",
    "llm", "large language model", "language model",
    "langchain", "llamaindex", "haystack",
    "huggingface", "replicate", "together.ai", "cohere",
    "ai agent", "ai workflow", "ai integration", "ai assistant",
    "openai api", "anthropic api", "azure openai",
    "watson", "ibm watson", "bedrock", "aws bedrock",
})

# SaaS apps that may send data to AI (source-side hints)
_SAAS_SOURCES = frozenset({
    "slack", "notion", "confluence", "jira", "google drive", "gdrive", "drive",
    "sharepoint", "teams", "salesforce", "hubspot", "zendesk",
    "dropbox", "box", "onedrive", "gmail", "outlook",
})

# Risk categories for findings
RISK_SHADOW_AI = "shadow_ai"
RISK_UNAPPROVED_AI = "unapproved_ai_integration"
RISK_DATA_TO_AI = "enterprise_data_to_ai"
RISK_AI_COPILOT = "ai_copilot_integration"


def _severity_to_risk(severity: int) -> RiskLevel:
    if severity >= 5:
        return "CRITICAL"
    if severity >= 4:
        return "HIGH"
    if severity >= 3:
        return "MEDIUM"
    if severity >= 2:
        return "LOW"
    return "MINIMAL"


@dataclass
class AIFinding:
    """Single AI-related risk finding."""

    category: str = ""  # One of RISK_* constants
    severity: int = 4
    message: str = ""
    source_app: str = ""
    target_or_service: str = ""
    evidence: str = ""
    rule_id: str = "ai_integration_risk"

    def to_text_finding(self, weight: float = 20.0) -> TextFinding:
        return TextFinding(
            rule_id=self.rule_id,
            category="ai_governance",
            severity=self.severity,
            weight=weight,
            evidence=self.evidence or self.message,
        )


@dataclass
class AIIntegrationsResult:
    """Result of AI + SaaS data flow analysis."""

    findings: list[AIFinding] = field(default_factory=list)
    ai_risk_score: float = 0.0
    shadow_ai_detected: bool = False
    unapproved_ai_detected: bool = False
    enterprise_data_to_ai: bool = False

    def to_text_findings(self, weight: float = 20.0) -> list[TextFinding]:
        return [f.to_text_finding(weight=weight) for f in self.findings]


def _iter_nodes(value: Any):
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from _iter_nodes(nested)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_nodes(item)


def _text_contains_ai_indicators(text: str) -> list[tuple[str, int]]:
    """Return list of (matched_phrase, severity)."""
    if not text or not isinstance(text, str):
        return []
    lower = text.lower()
    out: list[tuple[str, int]] = []
    for term in _AI_SYSTEMS:
        if term in lower:
            # Prefer whole-word or known phrases
            pattern = re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE)
            if pattern.search(lower):
                sev = 5 if term in ("openai", "anthropic", "claude", "chatgpt", "copilot") else 4
                out.append((term, sev))
    return out


def _check_payload_for_ai(
    payload: Any,
    source_app: str | None,
    destination_app: str | None,
    integration_id: str,
) -> AIIntegrationsResult:
    """Scan payload for AI systems and data flow to AI."""
    result = AIIntegrationsResult()
    seen_evidence: set[str] = set()

    def add_finding(category: str, severity: int, message: str, evidence: str, source: str, target: str):
        key = f"{category}:{evidence[:60]}"
        if key in seen_evidence:
            return
        seen_evidence.add(key)
        result.findings.append(
            AIFinding(
                category=category,
                severity=severity,
                message=message,
                source_app=source,
                target_or_service=target,
                evidence=evidence[:200],
                rule_id=f"ai_{category}",
            )
        )

    source_norm = (source_app or "").strip().lower()
    dest_norm = (destination_app or "").strip().lower()

    # 1) Explicit destination is an AI system
    if dest_norm in _AI_SYSTEMS or any(ai in dest_norm for ai in _AI_SYSTEMS):
        result.enterprise_data_to_ai = True
        result.unapproved_ai_detected = True
        add_finding(
            RISK_DATA_TO_AI,
            5,
            f"Integration sends data to AI/LLM system: {destination_app}",
            f"destination_app={destination_app or 'unknown'}",
            source_norm or "unknown",
            dest_norm,
        )

    # 2) Source is SaaS and we see AI-related keys in payload
    for node in _iter_nodes(payload):
        if not isinstance(node, dict):
            continue
        for key, value in node.items():
            key_lower = key.lower()
            val_str = str(value).lower() if value is not None else ""
            # API endpoint / provider fields
            if any(ai in key_lower for ai in ("openai", "anthropic", "llm", "ai_", "copilot", "api_provider")):
                result.shadow_ai_detected = True
                add_finding(
                    RISK_SHADOW_AI,
                    4,
                    f"AI/LLM provider reference in integration config: {key}",
                    f"{key}={str(value)[:80]}",
                    source_norm or "unknown",
                    val_str[:80],
                )
            if key_lower in ("provider", "model", "service") and _text_contains_ai_indicators(val_str):
                result.unapproved_ai_detected = True
                for phrase, sev in _text_contains_ai_indicators(val_str):
                    add_finding(
                        RISK_UNAPPROVED_AI,
                        sev,
                        f"Unapproved AI service reference: {phrase}",
                        f"{key}={value}",
                        source_norm or "unknown",
                        phrase,
                    )
            # Webhook / callback to AI
            if key_lower in ("webhook_url", "callback_url", "endpoint", "api_url") and _text_contains_ai_indicators(val_str):
                result.enterprise_data_to_ai = True
                add_finding(
                    RISK_DATA_TO_AI,
                    5,
                    "Webhook or API endpoint points to AI service",
                    f"{key}={str(value)[:100]}",
                    source_norm or "unknown",
                    "ai_service",
                )

    # 3) Integration ID or target name suggests SaaS -> AI
    id_lower = (integration_id or "").lower()
    for saas in _SAAS_SOURCES:
        for ai in _AI_SYSTEMS:
            if saas in id_lower and ai in id_lower:
                result.enterprise_data_to_ai = True
                add_finding(
                    RISK_DATA_TO_AI,
                    4,
                    f"SaaS-to-AI integration pattern: {integration_id}",
                    f"integration_id={integration_id}",
                    saas,
                    ai,
                )

    # Score
    if not result.findings:
        return result
    max_sev = max(f.severity for f in result.findings)
    base = {5: 70.0, 4: 50.0, 3: 30.0, 2: 15.0, 1: 5.0}.get(max_sev, 10.0)
    result.ai_risk_score = min(100.0, base + len(result.findings) * 8.0)
    result.shadow_ai_detected = result.shadow_ai_detected or any(f.category == RISK_SHADOW_AI for f in result.findings)
    result.unapproved_ai_detected = result.unapproved_ai_detected or any(f.category == RISK_UNAPPROVED_AI for f in result.findings)
    result.enterprise_data_to_ai = result.enterprise_data_to_ai or any(f.category == RISK_DATA_TO_AI for f in result.findings)
    return result


def _check_content_for_ai(content: str, location: str) -> AIIntegrationsResult:
    """Scan raw text content for AI-related patterns."""
    result = AIIntegrationsResult()
    if not content or not isinstance(content, str):
        return result
    matches = _text_contains_ai_indicators(content)
    seen: set[str] = set()
    for phrase, severity in matches:
        if phrase in seen:
            continue
        seen.add(phrase)
        result.findings.append(
            AIFinding(
                category=RISK_SHADOW_AI,
                severity=severity,
                message=f"AI/LLM reference in artifact: {phrase}",
                evidence=f"{location}: ...{phrase}...",
                rule_id="ai_shadow_usage",
            )
        )
    if result.findings:
        result.shadow_ai_detected = True
        result.unapproved_ai_detected = True
        max_sev = max(f.severity for f in result.findings)
        result.ai_risk_score = min(100.0, {5: 60.0, 4: 45.0, 3: 25.0}.get(max_sev, 15.0) + len(result.findings) * 5.0)
    return result


def detect_ai_integrations(
    payload: Any,
    content: str = "",
    *,
    integration_id: str = "",
    source_app: str | None = None,
    destination_app: str | None = None,
    content_location: str = "",
) -> AIIntegrationsResult:
    """Detect AI systems and copilots connected to SaaS or receiving enterprise data.

    Args:
        payload: Structured integration JSON/dict (e.g. from scan input).
        content: Raw text content to scan for AI references.
        integration_id: Scan target identifier.
        source_app: Optional source app from data flow analyzer.
        destination_app: Optional destination app from data flow analyzer.
        content_location: Label for content (e.g. target name) for findings.

    Returns:
        AIIntegrationsResult with findings (convertible to TextFinding),
        ai_risk_score, and flags for shadow_ai, unapproved_ai, enterprise_data_to_ai.
        Integrate by merging to_text_findings() into pipeline text_findings and
        adding context keys (ai_risk_detected, ai_findings_count, ai_risk_score).
    """
    result = _check_payload_for_ai(payload or {}, source_app, destination_app, integration_id or "")
    content_result = _check_content_for_ai(content or "", content_location or integration_id or "content")
    # Merge
    result.findings.extend(content_result.findings)
    result.shadow_ai_detected = result.shadow_ai_detected or content_result.shadow_ai_detected
    result.unapproved_ai_detected = result.unapproved_ai_detected or content_result.unapproved_ai_detected
    result.enterprise_data_to_ai = result.enterprise_data_to_ai or content_result.enterprise_data_to_ai
    if result.findings:
        max_sev = max(f.severity for f in result.findings)
        result.ai_risk_score = round(
            min(100.0, max(result.ai_risk_score, content_result.ai_risk_score) + 5.0 * (len(result.findings) - 1)),
            2,
        )
    return result
