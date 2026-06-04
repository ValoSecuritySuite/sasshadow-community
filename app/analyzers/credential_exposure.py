"""Credential exposure scanning module.

Detects exposed secrets in integration artifacts via:
- Regex detectors for AWS keys, OAuth tokens, API keys, private keys
- Entropy-based detection for unknown/high-entropy secrets
- Maps findings to affected SaaS integrations (source_app, destination_app, target).

Example finding:
  Type: AWS Access Key
  Risk: Critical
  Location: config.yaml
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger
from app.models.scan_models import CredentialFinding, RiskLevel, TextFinding

logger = get_logger(__name__)

# ── Risk level from severity 1–5 ─────────────────────────────────────────────

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


# ── Regex credential patterns ───────────────────────────────────────────────

@dataclass
class _PatternSpec:
    name: str
    credential_type: str
    pattern: str
    severity: int
    rule_id: str  # for TextFinding compatibility


_CREDENTIAL_PATTERNS: list[_PatternSpec] = [
    # AWS
    _PatternSpec(
        name="aws_access_key",
        credential_type="AWS Access Key",
        pattern=r"(?:AKIA|ASIA)[A-Z0-9]{16}",
        severity=5,
        rule_id="credential_aws_access_key",
    ),
    _PatternSpec(
        name="aws_secret_key",
        credential_type="AWS Secret Access Key",
        pattern=r'(?i)(?:aws_secret_access_key|aws_secret_key)\s*[:=]\s*["\']?[A-Za-z0-9/+=]{40}["\']?',
        severity=5,
        rule_id="credential_aws_secret_key",
    ),
    # OAuth / Bearer
    _PatternSpec(
        name="bearer_token",
        credential_type="OAuth Bearer Token",
        pattern=r"(?i)\bBearer\s+[A-Za-z0-9\-_.]{20,}\b",
        severity=5,
        rule_id="credential_bearer_token",
    ),
    _PatternSpec(
        name="client_secret",
        credential_type="OAuth Client Secret",
        pattern=r'(?i)client[_-]?secret\s*[:=]\s*["\']?[^\s"\'&]{8,}["\']?',
        severity=5,
        rule_id="credential_client_secret",
    ),
    _PatternSpec(
        name="refresh_token",
        credential_type="OAuth Refresh Token",
        pattern=r'(?i)refresh[_-]?token\s*[:=]\s*["\']?[^\s"\'&]{16,}["\']?',
        severity=5,
        rule_id="credential_refresh_token",
    ),
    _PatternSpec(
        name="access_token",
        credential_type="OAuth Access Token",
        pattern=r'(?i)access[_-]?token\s*[:=]\s*["\']?[A-Za-z0-9\-_.]{20,}["\']?',
        severity=5,
        rule_id="credential_access_token",
    ),
    # API keys
    _PatternSpec(
        name="api_key",
        credential_type="API Key",
        pattern=r'(?i)(?:api[_-]?key|x-api-key)\s*[:=]\s*["\']?[A-Za-z0-9\-_]{16,}["\']?',
        severity=5,
        rule_id="credential_api_key",
    ),
    _PatternSpec(
        name="github_pat",
        credential_type="GitHub Personal Access Token",
        pattern=r"gh[ps]_[A-Za-z0-9]{36,}",
        severity=5,
        rule_id="credential_github_pat",
    ),
    _PatternSpec(
        name="slack_token",
        credential_type="Slack Token",
        pattern=r"xox[baprs]-[A-Za-z0-9\-]{10,}",
        severity=5,
        rule_id="credential_slack_token",
    ),
    _PatternSpec(
        name="stripe_key",
        credential_type="Stripe API Key",
        pattern=r"(?:sk|pk)_(?:live|test)_[A-Za-z0-9]{24,}",
        severity=5,
        rule_id="credential_stripe_key",
    ),
    # Private keys
    _PatternSpec(
        name="private_key_pem",
        credential_type="Private Key (PEM)",
        pattern=r"-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----",
        severity=5,
        rule_id="credential_private_key_pem",
    ),
    _PatternSpec(
        name="openssh_private",
        credential_type="OpenSSH Private Key",
        pattern=r"-----BEGIN OPENSSH PRIVATE KEY-----",
        severity=5,
        rule_id="credential_openssh_private",
    ),
    # Token in URL
    _PatternSpec(
        name="token_in_url",
        credential_type="Token in URL",
        pattern=r"(?i)(?:access_token|token|api_key|apikey|secret)=[^\s&\"']{8,}",
        severity=4,
        rule_id="credential_token_in_url",
    ),
]

_EVIDENCE_MAX_LEN = 50
_ENTROPY_THRESHOLD = 4.3
_ENTROPY_MIN_LEN = 12


def _shannon_entropy(data: str) -> float:
    """Shannon entropy in bits per character."""
    if not data:
        return 0.0
    freq: dict[str, int] = {}
    for ch in data:
        freq[ch] = freq.get(ch, 0) + 1
    length = len(data)
    return -sum((count / length) * math.log2(count / length) for count in freq.values())


def _redact_evidence(match: str) -> str:
    """Return a short, redacted evidence string for display."""
    s = match.strip()
    if len(s) <= _EVIDENCE_MAX_LEN:
        return s[:8] + "..." if len(s) > 12 else s
    return s[:8] + "..." + s[-4:] if len(s) > 12 else s[: _EVIDENCE_MAX_LEN]


def _line_number_at_offset(text: str, offset: int) -> int:
    """Return 1-based line number for character offset."""
    return text.count("\n", 0, max(0, offset)) + 1


# ── Scanner API ─────────────────────────────────────────────────────────────


@dataclass
class CredentialScanResult:
    """Result of credential exposure scan.

    findings: list of structured credential findings (Type, Risk, Location)
    credential_risk_score: 0–100 aggregate score
    findings_by_integration: optional mapping integration_id -> finding indices
    """

    findings: list[CredentialFinding] = field(default_factory=list)
    credential_risk_score: float = 0.0
    findings_by_integration: dict[str, list[int]] = field(default_factory=dict)

    def to_text_findings(self, weight: float = 20.0) -> list[TextFinding]:
        """Convert to TextFinding list for pipeline merge.

        Uses rule_id prefix 'credential_' so the existing credential_detector
        counts these as credential findings.
        """
        out: list[TextFinding] = []
        for f in self.findings:
            slug = (
                f.credential_type.lower()
                .replace(" ", "_")
                .replace("(", "")
                .replace(")", "")
                .replace("-", "_")
            )
            rule_id = "credential_" + slug[:50]
            out.append(
                TextFinding(
                    rule_id=rule_id,
                    category=f.detection_method,
                    severity=f.severity,
                    weight=weight,
                    evidence=f.evidence,
                    match_start=f.match_start,
                    match_end=f.match_end,
                )
            )
        return out


def scan_credentials(
    content: str,
    location: str = "",
    integration_context: dict[str, Any] | None = None,
) -> CredentialScanResult:
    """Run regex and entropy credential detection on content.

    Args:
        content: Raw text (e.g. serialized JSON/YAML/config).
        location: Artifact name for findings (e.g. config.yaml, integration_1).
        integration_context: Optional dict with target, source_app, destination_app
            to attach to each finding for mapping to affected integrations.

    Returns:
        CredentialScanResult with findings (Type, Risk, Location), risk score,
        and optional findings_by_integration mapping.
    """
    result = CredentialScanResult()
    seen_spans: set[tuple[int, int]] = set()

    # ── Regex detectors ─────────────────────────────────────────────────────
    for spec in _CREDENTIAL_PATTERNS:
        try:
            for match in re.finditer(spec.pattern, content):
                start, end = match.start(), match.end()
                if (start, end) in seen_spans:
                    continue
                seen_spans.add((start, end))
                line_ref = f"line {_line_number_at_offset(content, start)}" if content else ""
                loc = location or line_ref or "content"
                if location and line_ref:
                    loc = f"{location} ({line_ref})"
                result.findings.append(
                    CredentialFinding(
                        credential_type=spec.credential_type,
                        risk=_severity_to_risk(spec.severity),
                        location=loc,
                        evidence=_redact_evidence(match.group()),
                        match_start=start,
                        match_end=end,
                        severity=spec.severity,
                        detection_method="regex",
                        integration_context=integration_context,
                    )
                )
        except re.error:
            logger.debug("Invalid regex in credential pattern %s", spec.name)

    # ── Entropy-based detection ─────────────────────────────────────────────
    for match in re.finditer(r'["\']([A-Za-z0-9_\-./+=]{' + str(_ENTROPY_MIN_LEN) + r',})["\']', content):
        candidate = match.group(1)
        if _shannon_entropy(candidate) < _ENTROPY_THRESHOLD:
            continue
        start, end = match.start(1), match.end(1)
        if (start, end) in seen_spans:
            continue
        # Avoid flagging UUIDs / hex as secrets
        if re.match(r"^[0-9a-fA-F\-]{36}$", candidate) or re.match(r"^[0-9a-fA-F]{32,64}$", candidate):
            continue
        seen_spans.add((start, end))
        line_ref = f"line {_line_number_at_offset(content, start)}" if content else ""
        loc = location or line_ref or "content"
        if location and line_ref:
            loc = f"{location} ({line_ref})"
        result.findings.append(
            CredentialFinding(
                credential_type="High-Entropy Secret (unknown type)",
                risk=_severity_to_risk(4),
                location=loc,
                evidence=_redact_evidence(candidate),
                match_start=start,
                match_end=end,
                severity=4,
                detection_method="entropy",
                integration_context=integration_context,
            )
        )

    # Also scan unquoted word-like tokens for high entropy
    for match in re.finditer(r"\b([A-Za-z0-9_\-./+=]{" + str(_ENTROPY_MIN_LEN) + r",})\b", content):
        candidate = match.group(1)
        if _shannon_entropy(candidate) < _ENTROPY_THRESHOLD:
            continue
        start, end = match.start(1), match.end(1)
        if (start, end) in seen_spans:
            continue
        if re.match(r"^[0-9a-fA-F\-]{36}$", candidate) or re.match(r"^[0-9a-fA-F]{32,64}$", candidate):
            continue
        seen_spans.add((start, end))
        line_ref = f"line {_line_number_at_offset(content, start)}" if content else ""
        loc = location or line_ref or "content"
        if location and line_ref:
            loc = f"{location} ({line_ref})"
        result.findings.append(
            CredentialFinding(
                credential_type="High-Entropy Secret (unknown type)",
                risk=_severity_to_risk(4),
                location=loc,
                evidence=_redact_evidence(candidate),
                match_start=start,
                match_end=end,
                severity=4,
                detection_method="entropy",
                integration_context=integration_context,
            )
        )

    # ── Risk score ───────────────────────────────────────────────────────────
    if not result.findings:
        return result
    max_sev = max(f.severity for f in result.findings)
    base = {5: 60.0, 4: 45.0, 3: 30.0, 2: 15.0, 1: 5.0}.get(max_sev, 10.0)
    breadth = min(len(set(f.credential_type for f in result.findings)) * 8.0, 25.0)
    count_bonus = min(len(result.findings) * 3.0, 15.0)
    result.credential_risk_score = round(min(100.0, base + breadth + count_bonus), 2)

    # ── Map findings to integration ─────────────────────────────────────────
    if integration_context and (integration_context.get("target") or integration_context.get("source_app")):
        integration_id = (
            integration_context.get("target")
            or f"{integration_context.get('source_app', '')}_to_{integration_context.get('destination_app', '')}"
        )
        result.findings_by_integration[integration_id] = list(range(len(result.findings)))

    return result
