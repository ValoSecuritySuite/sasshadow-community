"""Credential exposure detector.

Scans raw content and structured payloads for exposed credentials —
API keys, bearer tokens, client secrets, passwords, and high-entropy
strings that resemble leaked secrets.  Works in concert with the
text-scan rule engine for regex/keyword/entropy detection, then
augments results with credential-specific counting and risk scoring.
"""

from __future__ import annotations

from app.core.logging import get_logger
from app.models.scan_models import CredentialExposure, TextFinding, TextScanResult

logger = get_logger(__name__)

_CREDENTIAL_MARKERS = (
    "token", "secret", "password", "api_key",
    "credential", "entropy", "bearer", "client_secret",
)

_EXPOSURE_TYPE_MAP = {
    "saas_bearer_token": "bearer_token_exposed",
    "saas_api_key_assignment": "api_key_exposed",
    "saas_oauth_client_secret": "client_secret_exposed",
    "saas_oauth_refresh_token": "refresh_token_exposed",
    "saas_token_in_url": "token_in_url",
    "saas_webhook_secret_in_url": "webhook_secret_in_url",
    "saas_password_keyword": "password_reference",
    "saas_secret_keyword": "secret_reference",
    "saas_private_key_keyword": "private_key_reference",
    "saas_private_key_block": "private_key_exposed",
    "saas_high_entropy_credential": "high_entropy_credential",
    "saas_aws_access_key": "aws_key_exposed",
    "saas_github_pat": "github_token_exposed",
    "saas_slack_token": "slack_token_exposed",
}


def detect_credential_exposure(text_scan_result: TextScanResult) -> CredentialExposure:
    """Analyze text-scan findings for credential exposure.

    Filters findings to those matching credential-related rule IDs,
    classifies exposure types, and computes a credential risk score.
    """
    credential_findings: list[TextFinding] = []
    exposure_types: set[str] = set()

    for finding in text_scan_result.findings:
        is_credential = any(marker in finding.rule_id for marker in _CREDENTIAL_MARKERS)
        if not is_credential:
            continue

        credential_findings.append(finding)
        exposure_type = _EXPOSURE_TYPE_MAP.get(finding.rule_id, "credential_detected")
        exposure_types.add(exposure_type)

    if not credential_findings:
        return CredentialExposure()

    max_sev = max(f.severity for f in credential_findings)
    base = {5: 60.0, 4: 45.0, 3: 30.0, 2: 15.0, 1: 5.0}.get(max_sev, 10.0)
    breadth_bonus = min(len(exposure_types) * 8.0, 25.0)
    count_bonus = min(len(credential_findings) * 3.0, 15.0)
    credential_risk_score = round(min(100.0, base + breadth_bonus + count_bonus), 2)

    sorted_types = sorted(exposure_types)

    return CredentialExposure(
        exposed_credentials=len(credential_findings),
        exposure_types=sorted_types,
        findings=credential_findings,
        credential_risk_score=credential_risk_score,
    )


def count_credential_exposure_findings(findings: list[TextFinding]) -> int:
    """Count findings that match credential-related markers."""
    return sum(
        1 for finding in findings
        if any(marker in finding.rule_id for marker in _CREDENTIAL_MARKERS)
    )
