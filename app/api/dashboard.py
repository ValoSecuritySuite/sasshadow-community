"""Basic dashboard REST surface (Community Edition).

All routes live under ``/dashboard/*`` and stream pre-computed DTOs from
:mod:`app.services.dashboard_metrics`. Endpoints are guarded by
``settings.dashboard_enabled`` (returns 404 when disabled).
"""

import csv
import io
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app.core.config import settings
from app.core.limiter import limiter
from app.schemas_dashboard import (
    CriticalFindingsResponse,
    DashboardOverview,
    RiskDistribution,
    RiskTrendResponse,
)
from app.services import dashboard_metrics

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _ensure_enabled() -> None:
    if not settings.dashboard_enabled:
        raise HTTPException(status_code=404, detail="Dashboard disabled")


def _window_days(window: Optional[str]) -> int:
    return dashboard_metrics._window_to_days(
        window, default=settings.dashboard_default_window
    )


# ── JSON endpoints ──────────────────────────────────────────────────────────


@router.get("/overview", response_model=DashboardOverview)
@limiter.limit("60/minute")
def dashboard_overview(
    request: Request,
    window: Optional[str] = Query(default=None, description="e.g. 24h, 7d, 30d, 90d, all"),
) -> DashboardOverview:
    """Top-of-page KPI summary."""
    _ensure_enabled()
    return dashboard_metrics.compute_overview(_window_days(window))


@router.get("/risk-trend", response_model=RiskTrendResponse)
@limiter.limit("60/minute")
def dashboard_risk_trend(
    request: Request,
    window: Optional[str] = Query(default=None),
    bucket: Literal["hour", "day", "week"] = Query(default="day"),
) -> RiskTrendResponse:
    """Time series of average and max risk score over the window."""
    _ensure_enabled()
    return dashboard_metrics.compute_risk_trend(_window_days(window), bucket)


@router.get("/risk-distribution", response_model=RiskDistribution)
@limiter.limit("60/minute")
def dashboard_risk_distribution(request: Request) -> RiskDistribution:
    """Integrations per risk level (latest scan per target)."""
    _ensure_enabled()
    return dashboard_metrics.compute_risk_distribution()


@router.get("/critical", response_model=CriticalFindingsResponse)
@limiter.limit("60/minute")
def dashboard_critical(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
) -> CriticalFindingsResponse:
    """Most recent CRITICAL / HIGH findings across the portfolio."""
    _ensure_enabled()
    return dashboard_metrics.compute_recent_critical(limit=limit)


# ── Exports ─────────────────────────────────────────────────────────────────


_CSV_PANELS = {"overview", "trend", "distribution", "critical"}


def _csv_rows_for_panel(panel: str, window_days: int) -> list[list[str]]:
    if panel == "overview":
        o = dashboard_metrics.compute_overview(window_days)
        return [
            ["metric", "value"],
            ["window_days", str(o.window_days)],
            ["scans_total", str(o.scans_total)],
            ["scans_in_window", str(o.scans_in_window)],
            ["integrations_tracked", str(o.integrations_tracked)],
            ["integrations_in_window", str(o.integrations_in_window)],
            ["avg_risk_score", f"{o.avg_risk_score:.2f}"],
            ["median_risk_score", f"{o.median_risk_score:.2f}"],
            ["portfolio_risk_level", o.portfolio_risk_level],
            ["critical_integrations", str(o.critical_integrations)],
            ["risk_delta_vs_prior_window", f"{o.risk_delta_vs_prior_window:+.2f}"],
        ]
    if panel == "trend":
        t = dashboard_metrics.compute_risk_trend(window_days)
        rows = [["bucket_start", "avg_risk_score", "max_risk_score", "scans"]]
        for p in t.points:
            rows.append([
                p.bucket_start.isoformat(),
                f"{p.avg_risk_score:.2f}",
                f"{p.max_risk_score:.2f}",
                str(p.scans),
            ])
        return rows
    if panel == "distribution":
        d = dashboard_metrics.compute_risk_distribution()
        rows = [["risk_level", "count"]]
        for entry in d.entries:
            rows.append([entry.risk_level, str(entry.count)])
        return rows
    if panel == "critical":
        cr = dashboard_metrics.compute_recent_critical(limit=50)
        rows = [["scan_id", "target", "severity", "risk_level", "risk_score", "summary"]]
        for f in cr.findings:
            rows.append([
                f.scan_id,
                f.target,
                str(f.severity),
                f.risk_level,
                f"{f.risk_score:.2f}",
                f.summary,
            ])
        return rows
    return [["metric", "value"]]


@router.get("/export.csv")
@limiter.limit("30/minute")
def dashboard_export_csv(
    request: Request,
    panel: str = Query(..., description=f"One of: {', '.join(sorted(_CSV_PANELS))}"),
    window: Optional[str] = Query(default=None),
) -> StreamingResponse:
    """Stream a per-panel CSV export."""
    _ensure_enabled()
    if panel not in _CSV_PANELS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown panel '{panel}'. Allowed: {sorted(_CSV_PANELS)}",
        )
    days = _window_days(window)
    rows = _csv_rows_for_panel(panel, days)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerows(rows)
    payload = buf.getvalue().encode("utf-8")
    filename = f"saasshadow-dashboard-{panel}.csv"
    return StreamingResponse(
        iter([payload]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export.json")
@limiter.limit("30/minute")
def dashboard_export_json(
    request: Request,
    window: Optional[str] = Query(default=None),
) -> JSONResponse:
    """Composite snapshot: every panel returned in one payload."""
    _ensure_enabled()
    days = _window_days(window)
    overview = dashboard_metrics.compute_overview(days)
    trend = dashboard_metrics.compute_risk_trend(days)
    distribution = dashboard_metrics.compute_risk_distribution()
    critical = dashboard_metrics.compute_recent_critical(limit=20)
    return JSONResponse(
        {
            "window_days": days,
            "overview": overview.model_dump(mode="json"),
            "trend": trend.model_dump(mode="json"),
            "distribution": distribution.model_dump(mode="json"),
            "critical": critical.model_dump(mode="json"),
        }
    )


@router.post("/cache/clear")
@limiter.limit("12/minute")
def dashboard_clear_cache(request: Request) -> JSONResponse:
    """Drop the metrics cache (useful after seeding new test data)."""
    _ensure_enabled()
    dashboard_metrics.clear_cache()
    return JSONResponse({"cleared": True})


__all__ = ["router"]
