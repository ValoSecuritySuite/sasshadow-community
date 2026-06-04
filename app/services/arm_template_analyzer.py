"""ARM template and connector wiring analyzer.

Detects security issues in Azure Resource Manager (ARM) templates,
Logic Apps workflow definitions, and related connector wiring artifacts:

- ``$connections`` objects referencing managed API connections
- Parameters using ``string`` type instead of ``secureString`` for secrets
- Inline credentials in Logic Apps action ``authentication`` blocks
- Connection strings embedded in parameter default values
"""

from __future__ import annotations

import re
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

_SECRET_PARAM_KEYWORDS = {
    "password", "secret", "key", "token", "credential",
    "connectionstring", "connection_string", "accesskey",
    "access_key", "apikey", "api_key", "sas",
}

_SECURE_TYPES = {"securestring", "secureobject"}


class ARMAnalysisResult:
    """Structured result from ARM template / connector wiring analysis."""

    __slots__ = (
        "is_arm_template", "connections_found", "insecure_params",
        "inline_credentials", "connection_strings_in_defaults",
        "findings", "arm_risk_score",
    )

    def __init__(self) -> None:
        self.is_arm_template: bool = False
        self.connections_found: list[str] = []
        self.insecure_params: list[dict[str, str]] = []
        self.inline_credentials: list[dict[str, str]] = []
        self.connection_strings_in_defaults: list[dict[str, str]] = []
        self.findings: list[str] = []
        self.arm_risk_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_arm_template": self.is_arm_template,
            "connections_found": self.connections_found,
            "insecure_params": self.insecure_params,
            "inline_credentials": self.inline_credentials,
            "connection_strings_in_defaults": self.connection_strings_in_defaults,
            "findings": self.findings,
            "arm_risk_score": self.arm_risk_score,
        }


def _iter_nodes(value: Any):
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from _iter_nodes(nested)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_nodes(item)


def _looks_like_arm(payload: dict) -> bool:
    schema = str(payload.get("$schema", ""))
    if "deploymentTemplate" in schema or "management.azure.com" in schema:
        return True
    if "resources" in payload and "parameters" in payload:
        return True
    return False


def _check_connections(payload: dict, result: ARMAnalysisResult) -> None:
    for node in _iter_nodes(payload):
        if not isinstance(node, dict):
            continue
        connections = node.get("$connections")
        if not isinstance(connections, dict):
            continue
        value_block = connections.get("value", connections)
        if not isinstance(value_block, dict):
            continue
        for conn_name, conn_def in value_block.items():
            if isinstance(conn_def, dict):
                conn_id = conn_def.get("connectionId", conn_def.get("id", ""))
                result.connections_found.append(conn_name)
                result.findings.append(
                    f"$connections reference: {conn_name} → {conn_id}"
                )


def _check_parameters(payload: dict, result: ARMAnalysisResult) -> None:
    params = payload.get("parameters", {})
    if not isinstance(params, dict):
        return
    for param_name, param_def in params.items():
        if not isinstance(param_def, dict):
            continue
        param_type = str(param_def.get("type", "")).lower()
        param_name_lower = param_name.lower()

        has_secret_keyword = any(kw in param_name_lower for kw in _SECRET_PARAM_KEYWORDS)

        if has_secret_keyword and param_type not in _SECURE_TYPES:
            result.insecure_params.append({
                "parameter": param_name,
                "type": param_type,
                "recommendation": "secureString",
            })
            result.findings.append(
                f"Insecure parameter type: '{param_name}' uses '{param_type}' "
                f"instead of 'secureString'"
            )

        default_val = param_def.get("defaultValue", "")
        if isinstance(default_val, str) and has_secret_keyword and len(default_val) > 5:
            result.connection_strings_in_defaults.append({
                "parameter": param_name,
                "default_length": str(len(default_val)),
            })
            result.findings.append(
                f"Secret in default value: '{param_name}' has a hardcoded default "
                f"({len(default_val)} chars)"
            )


def _check_inline_auth(payload: dict, result: ARMAnalysisResult) -> None:
    for node in _iter_nodes(payload):
        if not isinstance(node, dict):
            continue
        auth = node.get("authentication")
        if not isinstance(auth, dict):
            continue
        auth_type = str(auth.get("type", "")).lower()
        if auth_type in ("basic", "raw"):
            has_inline_secret = any(
                isinstance(auth.get(k), str) and len(auth.get(k, "")) > 3
                for k in ("password", "secret", "value", "pfx")
            )
            if has_inline_secret:
                action_name = node.get("name", node.get("type", "unknown"))
                result.inline_credentials.append({
                    "action": str(action_name),
                    "auth_type": auth_type,
                })
                result.findings.append(
                    f"Inline credential in '{action_name}' action "
                    f"(auth type: {auth_type})"
                )


def _check_connection_strings_in_content(content: str, result: ARMAnalysisResult) -> None:
    patterns = [
        (r'(?i)Server\s*=\s*[^;]+;\s*(?:Database|Initial Catalog)\s*=\s*[^;]+;\s*(?:User\s*Id|Uid)\s*=\s*[^;]+;\s*(?:Password|Pwd)\s*=\s*[^;"\s]+', "SQL connection string"),
        (r'(?i)AccountName\s*=\s*[^;]+;\s*AccountKey\s*=\s*[A-Za-z0-9+/=]{20,}', "Azure Storage connection string"),
        (r'(?i)DefaultEndpointsProtocol\s*=\s*https?;', "Azure Storage endpoint string"),
    ]
    for pat, label in patterns:
        if re.search(pat, content):
            result.findings.append(f"Embedded {label} detected in content")


def analyze_arm_template(
    content: str,
    payload: Any,
) -> ARMAnalysisResult:
    """Analyze an ARM template or Logic Apps workflow definition.

    Returns an :class:`ARMAnalysisResult` with findings. If the payload
    does not look like an ARM template, ``is_arm_template`` will be False
    and findings will only include content-level connection-string detection.
    """
    result = ARMAnalysisResult()

    if isinstance(payload, dict) and _looks_like_arm(payload):
        result.is_arm_template = True
        logger.info("ARM template detected — analyzing parameters and connections")
        _check_connections(payload, result)
        _check_parameters(payload, result)
        _check_inline_auth(payload, result)
    elif isinstance(payload, dict):
        _check_connections(payload, result)
        _check_inline_auth(payload, result)

    _check_connection_strings_in_content(content, result)

    score = 0.0
    if result.insecure_params:
        score += min(len(result.insecure_params) * 15.0, 40.0)
    if result.inline_credentials:
        score += min(len(result.inline_credentials) * 20.0, 40.0)
    if result.connection_strings_in_defaults:
        score += min(len(result.connection_strings_in_defaults) * 15.0, 30.0)
    if result.connections_found:
        score += 5.0
    result.arm_risk_score = round(min(100.0, score), 2)

    return result
