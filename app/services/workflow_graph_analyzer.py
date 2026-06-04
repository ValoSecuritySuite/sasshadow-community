"""Workflow graph analyzer for automation platform exports.

Parses workflow definitions from n8n, Node-RED, Azure Logic Apps, and
AWS Step Functions to extract:

- SaaS connector nodes and their target services
- Credentials referenced in node parameters
- Data flow edges between services
- Webhook URLs with embedded secrets

The analyzer infers ``source_app`` / ``destination_app`` pairs from the
workflow graph when they aren't explicitly declared, feeding richer
context into the existing data-flow risk engine.
"""

from __future__ import annotations

import re
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


class WorkflowFinding:
    __slots__ = ("node_name", "node_type", "category", "detail", "severity")

    def __init__(
        self,
        node_name: str,
        node_type: str,
        category: str,
        detail: str,
        severity: int = 3,
    ) -> None:
        self.node_name = node_name
        self.node_type = node_type
        self.category = category
        self.detail = detail
        self.severity = severity

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_name": self.node_name,
            "node_type": self.node_type,
            "category": self.category,
            "detail": self.detail,
            "severity": self.severity,
        }


class WorkflowAnalysisResult:
    __slots__ = (
        "platform", "node_count", "saas_connectors",
        "inferred_services", "credential_refs", "webhook_urls",
        "findings", "workflow_risk_score",
    )

    def __init__(self) -> None:
        self.platform: str | None = None
        self.node_count: int = 0
        self.saas_connectors: list[str] = []
        self.inferred_services: list[str] = []
        self.credential_refs: list[str] = []
        self.webhook_urls: list[str] = []
        self.findings: list[WorkflowFinding] = []
        self.workflow_risk_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "node_count": self.node_count,
            "saas_connectors": self.saas_connectors,
            "inferred_services": sorted(set(self.inferred_services)),
            "credential_refs": self.credential_refs,
            "webhook_urls": self.webhook_urls,
            "findings": [f.to_dict() for f in self.findings],
            "workflow_risk_score": self.workflow_risk_score,
        }


# ── Platform-specific node type → SaaS service mappings ──────────────────────

_N8N_SERVICE_MAP: dict[str, str] = {
    "slack": "slack", "gmail": "gmail", "googlesheets": "google_sheets",
    "googledrive": "google_drive", "github": "github", "hubspot": "hubspot",
    "salesforce": "salesforce", "jira": "jira", "notion": "notion",
    "airtable": "airtable", "stripe": "stripe", "twilio": "twilio",
    "sendgrid": "sendgrid", "mailchimp": "mailchimp", "dropbox": "dropbox",
    "microsoftoutlook": "outlook", "microsoftteams": "teams",
    "microsoftonedrive": "onedrive", "aws": "aws", "azure": "azure",
    "googlebigquery": "bigquery", "mongodb": "mongodb", "postgres": "postgres",
    "mysql": "mysql", "httpRequest": "http_external", "webhook": "webhook",
}

_NODERED_SERVICE_MAP: dict[str, str] = {
    "slack": "slack", "email": "email", "twitter": "twitter",
    "mqtt": "mqtt", "http": "http_external", "websocket": "websocket",
    "mongodb": "mongodb", "mysql": "mysql", "postgres": "postgres",
}

_CREDENTIAL_KEYS = {
    "credentials", "credential", "authentication", "auth",
    "password", "secret", "apiKey", "api_key", "token",
    "access_token", "refresh_token", "client_secret",
}

_SECRET_URL_PATTERN = re.compile(
    r'(?i)https?://[^\s"\']*(?:secret|token|key|password|api_key)=[^\s"\'&]{6,}'
)


def _detect_platform(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        if isinstance(payload, list) and payload and isinstance(payload[0], dict):
            if "id" in payload[0] and "type" in payload[0] and "wires" in payload[0]:
                return "node-red"
        return None

    if "nodes" in payload and isinstance(payload.get("nodes"), list):
        first = payload["nodes"][0] if payload["nodes"] else {}
        if isinstance(first, dict) and "type" in first:
            return "n8n"

    if "definition" in payload and isinstance(payload.get("definition"), dict):
        defn = payload["definition"]
        if "triggers" in defn or "actions" in defn:
            return "logic-apps"

    if isinstance(payload.get("triggers"), dict) or isinstance(payload.get("actions"), dict):
        return "logic-apps"

    if "States" in payload or "StartAt" in payload:
        return "step-functions"

    return None


def _analyze_n8n(payload: dict, result: WorkflowAnalysisResult) -> None:
    nodes = payload.get("nodes", [])
    result.node_count = len(nodes)

    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_type = str(node.get("type", ""))
        node_name = str(node.get("name", node_type))
        type_lower = node_type.lower().replace("n8n-nodes-base.", "")

        service = _N8N_SERVICE_MAP.get(type_lower)
        if service:
            result.saas_connectors.append(f"{node_name}:{service}")
            result.inferred_services.append(service)

        params = node.get("parameters", {})
        if isinstance(params, dict):
            _scan_dict_for_creds(params, node_name, node_type, result)

        creds = node.get("credentials", {})
        if isinstance(creds, dict):
            for cred_type in creds:
                result.credential_refs.append(f"{node_name}:{cred_type}")


def _analyze_nodered(flows: list, result: WorkflowAnalysisResult) -> None:
    result.node_count = len(flows)

    for node in flows:
        if not isinstance(node, dict):
            continue
        node_type = str(node.get("type", ""))
        node_name = str(node.get("name", node_type))
        type_lower = node_type.lower().split(" ")[0]

        for key, service in _NODERED_SERVICE_MAP.items():
            if key in type_lower:
                result.saas_connectors.append(f"{node_name}:{service}")
                result.inferred_services.append(service)
                break

        _scan_dict_for_creds(node, node_name, node_type, result)


def _analyze_logic_apps(payload: dict, result: WorkflowAnalysisResult) -> None:
    defn = payload.get("definition", payload)
    if not isinstance(defn, dict):
        return

    actions = defn.get("actions", {})
    triggers = defn.get("triggers", {})

    all_steps = {}
    if isinstance(actions, dict):
        all_steps.update(actions)
    if isinstance(triggers, dict):
        all_steps.update(triggers)

    result.node_count = len(all_steps)

    for step_name, step_def in all_steps.items():
        if not isinstance(step_def, dict):
            continue
        step_type = str(step_def.get("type", ""))
        api_conn = step_def.get("inputs", {})
        if isinstance(api_conn, dict):
            host = api_conn.get("host", {})
            if isinstance(host, dict):
                conn = host.get("connection", {})
                if isinstance(conn, dict):
                    conn_name = conn.get("name", "")
                    if conn_name:
                        result.saas_connectors.append(f"{step_name}:{conn_name}")
                        result.inferred_services.append(
                            str(conn_name).split("/")[-1].lower()
                        )

            _scan_dict_for_creds(api_conn, step_name, step_type, result)

        auth = step_def.get("inputs", {}).get("authentication", {}) if isinstance(step_def.get("inputs"), dict) else {}
        if isinstance(auth, dict) and auth:
            auth_type = auth.get("type", "unknown")
            result.credential_refs.append(f"{step_name}:auth({auth_type})")


def _analyze_step_functions(payload: dict, result: WorkflowAnalysisResult) -> None:
    states = payload.get("States", {})
    if not isinstance(states, dict):
        return

    result.node_count = len(states)

    for state_name, state_def in states.items():
        if not isinstance(state_def, dict):
            continue
        resource = str(state_def.get("Resource", ""))
        if resource.startswith("arn:aws:"):
            parts = resource.split(":")
            service = parts[2] if len(parts) > 2 else "unknown"
            result.saas_connectors.append(f"{state_name}:{service}")
            result.inferred_services.append(service)

        params = state_def.get("Parameters", {})
        if isinstance(params, dict):
            _scan_dict_for_creds(params, state_name, "State", result)


def _scan_dict_for_creds(
    d: dict,
    node_name: str,
    node_type: str,
    result: WorkflowAnalysisResult,
) -> None:
    for key, value in d.items():
        key_lower = key.lower()
        if key_lower in _CREDENTIAL_KEYS and isinstance(value, str) and len(value) > 5:
            result.findings.append(WorkflowFinding(
                node_name=node_name,
                node_type=node_type,
                category="inline_credential",
                detail=f"Credential key '{key}' has inline value ({len(value)} chars)",
                severity=4,
            ))
        if isinstance(value, str):
            for match in _SECRET_URL_PATTERN.finditer(value):
                result.webhook_urls.append(match.group())
                result.findings.append(WorkflowFinding(
                    node_name=node_name,
                    node_type=node_type,
                    category="webhook_secret",
                    detail=f"Webhook URL with embedded secret in '{key}'",
                    severity=4,
                ))
        if isinstance(value, dict):
            _scan_dict_for_creds(value, node_name, node_type, result)


def analyze_workflow(
    content: str,
    payload: Any,
) -> WorkflowAnalysisResult:
    """Analyze a workflow export for SaaS connectors, credentials, and data flow.

    Supports n8n, Node-RED, Azure Logic Apps, and AWS Step Functions.
    Returns an :class:`WorkflowAnalysisResult` with platform detection,
    connector enumeration, and credential findings.
    """
    result = WorkflowAnalysisResult()
    platform = _detect_platform(payload)

    if platform is None:
        return result

    result.platform = platform
    logger.info("Workflow platform detected: %s", platform)

    if platform == "n8n" and isinstance(payload, dict):
        _analyze_n8n(payload, result)
    elif platform == "node-red" and isinstance(payload, list):
        _analyze_nodered(payload, result)
    elif platform == "logic-apps" and isinstance(payload, dict):
        _analyze_logic_apps(payload, result)
    elif platform == "step-functions" and isinstance(payload, dict):
        _analyze_step_functions(payload, result)

    # Score
    score = 0.0
    if result.findings:
        high_sev = [f for f in result.findings if f.severity >= 4]
        score += min(len(high_sev) * 15.0, 50.0)
        score += min((len(result.findings) - len(high_sev)) * 5.0, 20.0)
    if result.webhook_urls:
        score += min(len(result.webhook_urls) * 10.0, 20.0)
    if result.credential_refs:
        score += min(len(result.credential_refs) * 3.0, 10.0)
    result.workflow_risk_score = round(min(100.0, score), 2)

    return result
