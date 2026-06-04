"""Microsoft Entra (Azure AD) connector.

Uses client credentials to obtain a token, then calls Microsoft Graph
to list app registrations (with requiredResourceAccess and passwordCredentials).
Each app is normalized to pipeline json_data shape and scanned.
"""

from __future__ import annotations

import json
import urllib.parse
from typing import Any

from app.connectors.base import http_get
from app.core.logging import get_logger

logger = get_logger(__name__)

_GRAPH_BASE = "https://graph.microsoft.com/v1.0"
_TOKEN_URL_TEMPLATE = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"


def _get_token(tenant_id: str, client_id: str, client_secret: str) -> str:
    """OAuth2 client credentials flow; returns access_token."""
    url = _TOKEN_URL_TEMPLATE.format(tenant_id=tenant_id)
    body = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": "https://graph.microsoft.com/.default",
    }).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req, timeout=30) as resp:
        if resp.status >= 400:
            raise RuntimeError(f"Entra token request failed: HTTP {resp.status}")
        out = json.loads(resp.read().decode("utf-8"))
    token = out.get("access_token")
    if not token:
        raise RuntimeError("Entra token response missing access_token")
    return token


def _list_applications(access_token: str) -> list[dict[str, Any]]:
    """Fetch all applications from Graph (paginated). Select fields needed for scanning."""
    select = "id,displayName,appId,requiredResourceAccess,passwordCredentials,createdDateTime"
    url = f"{_GRAPH_BASE}/applications?$select={select}&$top=999"
    headers = {"Authorization": f"Bearer {access_token}"}
    all_apps: list[dict[str, Any]] = []
    while url:
        data = http_get(url, headers=headers)
        all_apps.extend(data.get("value") or [])
        url = data.get("@odata.nextLink") or None
    return all_apps


def _normalize_app_for_pipeline(app: dict[str, Any]) -> dict[str, Any]:
    """Build json_data shape for pipeline. Redact secret values; keep requiredResourceAccess for Entra parser."""
    # Redact passwordCredentials: keep only metadata (displayName, endDateTime) for risk signals
    pcs = app.get("passwordCredentials") or []
    safe_pcs = []
    for pc in pcs:
        if isinstance(pc, dict):
            safe_pcs.append({
                "displayName": pc.get("displayName"),
                "endDateTime": pc.get("endDateTime"),
                "keyId": pc.get("keyId"),
            })
    out: dict[str, Any] = {
        "source_app": "microsoft_entra",
        "destination_app": "",
        "requiredResourceAccess": app.get("requiredResourceAccess") or [],
        "passwordCredentials": safe_pcs,
        "displayName": app.get("displayName"),
        "appId": app.get("appId"),
    }
    if app.get("createdDateTime"):
        out["last_updated"] = app["createdDateTime"]
    return out


def fetch_entra_integrations(
    tenant_id: str,
    client_id: str,
    client_secret: str,
) -> list[tuple[str, dict[str, Any]]]:
    """Fetch all Entra app registrations and return list of (target, json_data) for pipeline.

    Raises on auth or Graph errors.
    """
    token = _get_token(tenant_id, client_id, client_secret)
    apps = _list_applications(token)
    out: list[tuple[str, dict[str, Any]]] = []
    for app in apps:
        app_id = app.get("appId") or app.get("id") or "unknown"
        display = (app.get("displayName") or "").strip() or app_id
        target = f"entra_{app_id}"
        json_data = _normalize_app_for_pipeline(app)
        json_data["displayName"] = display
        out.append((target, json_data))
    return out


def sync_entra(
    tenant_id: str,
    client_id: str,
    client_secret: str,
    *,
    customer_id: str | None = None,
    run_pipeline_and_store: Any = None,
) -> tuple[int, list[dict[str, Any]], list[str]]:
    """Fetch Entra apps, run pipeline for each, and store results.

    run_pipeline_and_store(target, json_data, customer_id) must be provided
    by the API layer; it runs the pipeline and persists the scan.

    Returns (synced_count, scans, errors).
    """
    if run_pipeline_and_store is None:
        raise ValueError("run_pipeline_and_store is required")
    try:
        items = fetch_entra_integrations(tenant_id, client_id, client_secret)
    except Exception as e:
        logger.warning("Entra fetch failed: %s", e)
        return 0, [], [str(e)]
    scans: list[dict[str, Any]] = []
    errors: list[str] = []
    for target, json_data in items:
        try:
            scan_info = run_pipeline_and_store(target=target, json_data=json_data, customer_id=customer_id)
            if scan_info:
                scans.append(scan_info)
        except Exception as e:
            errors.append(f"{target}: {e}")
            logger.debug("Entra scan failed for %s: %s", target, e)
    return len(scans), scans, errors
