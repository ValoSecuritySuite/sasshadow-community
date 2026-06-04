"""Compliance and governance framework mapping.

Maps scan findings to SOC 2, ISO 27001, and NIST AI RMF with
control references, rationale, severity, and remediation text.
Output is reusable in JSON and PDF reports.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class FrameworkMapping(BaseModel):
    """A single mapping of a finding to a framework control."""

    finding_type: str = Field(description="Finding type or rule_id that was mapped")
    framework: str = Field(description="Framework name: SOC2, ISO27001, NIST_AI_RMF")
    control_reference: str = Field(description="Control ID or criterion reference")
    rationale: str = Field(default="", description="Why this finding maps to this control")
    severity: int = Field(default=3, ge=1, le=5)
    recommended_remediation: str = Field(default="", description="Recommended remediation text")


class ComplianceMapping(BaseModel):
    """Aggregate compliance mapping result for a scan."""

    mappings: list[FrameworkMapping] = Field(default_factory=list)
    frameworks_covered: list[str] = Field(default_factory=list)


class FrameworkControlInfo(BaseModel):
    """A single control reference within a framework."""

    control_reference: str = Field(description="Control ID or criterion reference")
    rationale: str = Field(default="", description="Why findings map to this control")
    recommended_remediation: str = Field(default="", description="Recommended remediation text")


class SupportedFrameworkInfo(BaseModel):
    """A supported compliance framework with its control mappings."""

    framework: str = Field(description="Framework identifier: SOC2, ISO27001, NIST_AI_RMF")
    controls: list[FrameworkControlInfo] = Field(
        default_factory=list,
        description="List of control references and remediation guidance",
    )


class SupportedFrameworksResponse(BaseModel):
    """Response for GET /compliance/frameworks."""

    frameworks: list[SupportedFrameworkInfo] = Field(
        default_factory=list,
        description="Supported frameworks and their control IDs for UI or integrations",
    )


# ── Mapping table: rule_id / category patterns → framework controls ─────────
# Keys are lowercase rule_id prefixes or categories; values are list of
# (framework, control_ref, rationale, remediation_template)
_FRAMEWORK_RULES: list[tuple[list[str], str, str, str, str]] = [
    # OAuth / access control
    (["oauth", "over_permission", "scope"], "SOC2", "CC6.1", "Logical access is managed via OAuth; over-permissioned scopes violate least privilege.", "Apply least-privilege OAuth scopes; remove wildcard and admin scopes; implement incremental consent."),
    (["oauth", "over_permission", "scope"], "ISO27001", "A.9.4.1", "Information access restriction: OAuth scope over-permission weakens access control.", "Restrict OAuth scopes to minimum required; document and approve scope requests."),
    (["oauth", "client_secret", "saas_oauth"], "SOC2", "CC6.6", "Logical access credentials (client secrets) must be protected.", "Store OAuth client secrets in a secure vault; rotate regularly; avoid plaintext in configs."),
    (["oauth", "client_secret"], "ISO27001", "A.9.4.3", "Management of privileged access rights: secrets in configs violate secure management.", "Use a secrets manager; enforce rotation; audit access to secrets."),
    # Tokens
    (["token", "rotation", "long_lived", "bearer"], "SOC2", "CC6.1", "Token lifecycle and rotation support access control integrity.", "Enable token rotation; set TTLs under 90 days; implement revocation procedures."),
    (["token", "rotation", "long_lived"], "ISO27001", "A.9.4.2", "Secure log-on procedures: long-lived tokens increase credential abuse risk.", "Implement short-lived tokens and refresh rotation; monitor for anomalous use."),
    (["token", "url", "token_in_url"], "SOC2", "CC6.6", "Credentials in URLs are exposed in logs and referrers.", "Remove tokens from URL parameters; use Authorization headers or secure cookies."),
    (["token", "shared_across"], "SOC2", "CC6.2", "Shared tokens across integrations amplify blast radius of compromise.", "Issue unique tokens per integration; scope per service; revoke and re-issue if reuse detected."),
    # Credentials
    (["credential", "aws", "github", "slack", "stripe", "secret", "private_key"], "SOC2", "CC6.6", "Exposed credentials violate protection of confidential information.", "Rotate all exposed credentials immediately; store in vault; add static analysis to CI/CD."),
    (["credential", "aws", "github", "slack", "secret", "private_key"], "ISO27001", "A.9.4.1", "Access to information: credential exposure undermines access restriction.", "Rotate credentials; use managed secrets; restrict and audit access to secret storage."),
    (["credential", "entropy", "high_entropy"], "SOC2", "CC6.6", "High-entropy secrets in artifacts indicate possible credential exposure.", "Confirm whether value is a secret; if so, rotate and move to secure storage."),
    # Data flow
    (["data_flow", "cross_platform", "sensitive_data", "pii"], "SOC2", "CC6.7", "Transmission of sensitive data across systems must be authorized and protected.", "Document data flows; apply DLP at integration boundaries; verify recipient security posture."),
    (["data_flow", "cross_platform", "sensitive"], "ISO27001", "A.12.4.1", "Logging: cross-platform data flows should be logged and reviewed.", "Implement logging of integration data flows; classify data; enforce policies at boundaries."),
    (["data_flow", "pii", "customer_data"], "SOC2", "PI1.1", "Personal information collection and use must be disclosed and protected.", "Ensure data classification and consent; limit PII shared via integrations to what is necessary."),
    # AI
    (["ai_", "shadow_ai", "enterprise_data_to_ai", "unapproved_ai"], "NIST_AI_RMF", "GOVERN 1.2", "AI system risks must be identified and managed; shadow AI and unapproved AI use increase risk.", "Inventory AI-enabled integrations; approve and document AI data flows; restrict sensitive data to approved AI systems."),
    (["ai_", "shadow_ai", "enterprise_data_to_ai"], "NIST_AI_RMF", "MAP 1.1", "Context mapping: data flows to AI systems must be documented.", "Map which enterprise data is sent to which AI services; assess necessity and risk."),
    (["ai_", "enterprise_data_to_ai", "unapproved_ai"], "SOC2", "CC6.1", "Logical access to systems processing sensitive data (including AI) must be controlled.", "Restrict which AI systems receive enterprise data; use approved integrations only; monitor for shadow AI."),
    (["ai_", "enterprise_data_to_ai"], "ISO27001", "A.8.2.1", "Classification of information: data shared with AI must be classified and handled accordingly.", "Classify data sent to AI; prohibit or restrict high-sensitivity data to unapproved AI; document approvals."),
]


def _finding_matches_patterns(finding_type: str, category: str, patterns: list[str]) -> bool:
    """Return True if the finding type or category matches any of the pattern substrings."""
    combined = (finding_type or "").lower() + " " + (category or "").lower()
    return any(p in combined for p in patterns)


def map_findings_to_frameworks(
    findings: list[Any],
    *,
    include_ai_context: bool = True,
) -> ComplianceMapping:
    """Map a list of findings to governance frameworks (SOC 2, ISO 27001, NIST AI RMF).

    Args:
        findings: List of finding-like objects or dicts with rule_id, category,
                  severity, and optionally evidence. TextFinding or dict with
                  keys rule_id, category, severity.
        include_ai_context: If True, AI-related findings are also mapped to NIST AI RMF.

    Returns:
        ComplianceMapping with one or more FrameworkMapping entries per finding
        (finding_type, framework, control_reference, rationale, severity,
         recommended_remediation). Reusable in JSON and PDF reports.
    """
    result = ComplianceMapping()
    seen_keys: set[tuple[str, str, str]] = set()  # (finding_type, framework, control_ref)

    for f in findings:
        if hasattr(f, "rule_id"):
            finding_type = getattr(f, "rule_id", "") or ""
            category = getattr(f, "category", "") or ""
            severity = getattr(f, "severity", 3)
        elif isinstance(f, dict):
            finding_type = f.get("rule_id", "") or ""
            category = f.get("category", "") or ""
            severity = f.get("severity", 3)
        else:
            continue
        if not finding_type and not category:
            continue

        for patterns, framework, control_ref, rationale, remediation in _FRAMEWORK_RULES:
            if not include_ai_context and framework == "NIST_AI_RMF":
                continue
            if not _finding_matches_patterns(finding_type, category, patterns):
                continue
            key = (finding_type, framework, control_ref)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            result.mappings.append(
                FrameworkMapping(
                    finding_type=finding_type,
                    framework=framework,
                    control_reference=control_ref,
                    rationale=rationale,
                    severity=severity,
                    recommended_remediation=remediation,
                )
            )
            if framework not in result.frameworks_covered:
                result.frameworks_covered.append(framework)

    result.frameworks_covered.sort()
    return result


def get_supported_frameworks() -> SupportedFrameworksResponse:
    """Return supported compliance frameworks and their control IDs for API/docs.

    Builds a deduplicated list of (framework, control_reference) with rationale
    and remediation from the internal mapping table.
    """
    seen: dict[tuple[str, str], tuple[str, str]] = {}  # (framework, control_ref) -> (rationale, remediation)
    for patterns, framework, control_ref, rationale, remediation in _FRAMEWORK_RULES:
        key = (framework, control_ref)
        if key not in seen:
            seen[key] = (rationale, remediation)

    # Group by framework
    by_framework: dict[str, list[FrameworkControlInfo]] = {}
    for (framework, control_ref), (rationale, remediation) in seen.items():
        by_framework.setdefault(framework, []).append(
            FrameworkControlInfo(
                control_reference=control_ref,
                rationale=rationale,
                recommended_remediation=remediation,
            )
        )

    frameworks = [
        SupportedFrameworkInfo(
            framework=fw,
            controls=sorted(by_framework[fw], key=lambda c: c.control_reference),
        )
        for fw in sorted(by_framework.keys())
    ]
    return SupportedFrameworksResponse(frameworks=frameworks)
