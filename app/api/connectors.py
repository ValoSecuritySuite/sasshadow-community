"""Connector sync API — on-demand sync from Entra and Slack."""

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.connectors.entra import sync_entra
from app.connectors.slack import sync_slack
from app.core.limiter import limiter
from app.db.scan_history import insert_scan
from app.models.scan_models import PipelineRequest, ScanReport
from app.services.pipeline import run_pipeline
from app.services.rules_loader import load_rules

router = APIRouter(prefix="/connectors", tags=["Connectors"])


def _run_pipeline_and_store(
    target: str,
    json_data: dict[str, Any],
    customer_id: str | None,
) -> dict[str, Any] | None:
    """Run pipeline for one integration and persist. Returns {scan_id, target, risk_score} or None."""
    rules = load_rules(use_cache=False)
    payload = PipelineRequest(target=target, json_data=json_data, customer_id=customer_id)
    result = run_pipeline(payload, rule_set=rules)
    if result.report is None:
        return None
    report: ScanReport = result.report
    try:
        insert_scan(report, target=target, customer_id=customer_id)
    except Exception:
        pass
    return {"scan_id": report.scan_id, "target": target, "risk_score": report.risk_score}


# ---------------------------------------------------------------------------
# Request/response models
# ---------------------------------------------------------------------------

class EntraSyncRequest(BaseModel):
    tenant_id: str
    client_id: str
    client_secret: str
    customer_id: str | None = None


class SlackSyncRequest(BaseModel):
    token: str
    customer_id: str | None = None


class ConnectorSyncResponse(BaseModel):
    connector: str
    synced: int
    scans: list[dict[str, Any]]
    errors: list[str]


class ConnectorInfo(BaseModel):
    id: str
    name: str
    description: str


class ConnectorsListResponse(BaseModel):
    connectors: list[ConnectorInfo]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=ConnectorsListResponse, summary="List available connectors")
@limiter.limit("60/minute")
def list_connectors(request: Request) -> ConnectorsListResponse:
    """List connectors that can sync OAuth/integration data from external platforms."""
    return ConnectorsListResponse(
        connectors=[
            ConnectorInfo(
                id="entra",
                name="Microsoft Entra (Azure AD)",
                description="Sync app registrations from Microsoft Graph; discovers OAuth scopes and credentials metadata.",
            ),
            ConnectorInfo(
                id="slack",
                name="Slack",
                description="Sync the app associated with a bot/user token (auth.test + x-oauth-scopes).",
            ),
        ]
    )


@router.post("/entra/sync", response_model=ConnectorSyncResponse, summary="Sync from Microsoft Entra")
@limiter.limit("10/minute")
def entra_sync(request: Request, body: EntraSyncRequest) -> ConnectorSyncResponse:
    """Sync app registrations from Microsoft Entra (Azure AD) via Graph API.

    Uses client credentials (tenant_id, client_id, client_secret). Each app is
    scanned and stored in scan history. Requires Application.Read.All (or similar)
    on the app registration used for client_id.
    """
    synced, scans, errors = sync_entra(
        body.tenant_id,
        body.client_id,
        body.client_secret,
        customer_id=body.customer_id,
        run_pipeline_and_store=_run_pipeline_and_store,
    )
    return ConnectorSyncResponse(connector="entra", synced=synced, scans=scans, errors=errors)


@router.post("/slack/sync", response_model=ConnectorSyncResponse, summary="Sync from Slack")
@limiter.limit("20/minute")
def slack_sync(request: Request, body: SlackSyncRequest) -> ConnectorSyncResponse:
    """Sync the Slack app for the given token (auth.test + scopes from response header).

    The token must be a bot (xoxb-*) or user (xoxp-*) token. One integration is
    discovered and scanned, then stored in scan history.
    """
    synced, scans, errors = sync_slack(
        body.token,
        customer_id=body.customer_id,
        run_pipeline_and_store=_run_pipeline_and_store,
    )
    return ConnectorSyncResponse(connector="slack", synced=synced, scans=scans, errors=errors)
