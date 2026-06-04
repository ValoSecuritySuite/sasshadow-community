"""SaaSShadow scan API endpoints.

Provides the primary REST interface for SaaS integration risk analysis:
  - Single integration scan (OAuth, tokens, credentials, data flow)
  - Batch dataset analysis
  - JSON + PDF executive reporting
  - OAuth scope policy inspection
  - Scan results are persisted for history (GET /scans).
"""

import csv
import io
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.core.limiter import limiter
from app.db.scan_history import insert_scan
from app.models.scan_models import (
    DatasetAnalysisRequest,
    PipelineRequest,
    PipelineResult,
    ScanReport,
)
from app.services.dataset_analysis import analyze_dataset
from app.services.pdf_report_generator import generate_executive_pdf
from app.services.pipeline import run_pipeline
from app.services.rules_loader import load_rules

router = APIRouter(prefix="/scan", tags=["SaaS Integration Scanning"])


def _persist_scan(report: ScanReport, target: str, customer_id: str | None) -> None:
    """Persist scan to history DB (best-effort)."""
    try:
        insert_scan(report, target=target, customer_id=customer_id)
    except Exception:  # noqa: BLE001
        pass  # Do not fail the request if persistence fails


@router.post("/analyze", response_model=PipelineResult, summary="Scan a SaaS integration")
@limiter.limit("60/minute")
def analyze_integration(request: Request, payload: PipelineRequest) -> PipelineResult:
    """Run full SaaS integration analysis.

    Detects OAuth over-permission, API token misuse, credential exposure,
    and cross-platform data flow risks. Returns a composite 0-100 risk
    score with per-dimension breakdowns. Result is stored in scan history.
    """
    rules = load_rules(use_cache=False)
    result = run_pipeline(payload, rule_set=rules)
    if result.report is not None:
        _persist_scan(result.report, payload.target, payload.customer_id)
    return result


@router.post("/report/json", response_model=ScanReport, summary="JSON risk report")
@limiter.limit("60/minute")
def export_json_report(request: Request, payload: PipelineRequest) -> ScanReport:
    """Run analysis and return the structured JSON risk report. Result is stored in scan history."""
    rules = load_rules(use_cache=False)
    result = run_pipeline(payload, rule_set=rules)
    assert result.report is not None  # noqa: S101
    _persist_scan(result.report, payload.target, payload.customer_id)
    return result.report


@router.post("/report/pdf", response_class=StreamingResponse, summary="Executive PDF report")
@limiter.limit("20/minute")
def export_pdf_report(request: Request, payload: PipelineRequest) -> StreamingResponse:
    """Run analysis and return an executive-grade PDF risk report."""
    rules = load_rules(use_cache=False)
    result = run_pipeline(payload, rule_set=rules)
    assert result.report is not None  # noqa: S101
    pdf_bytes = generate_executive_pdf(result.report)
    filename = f"saas_risk_report_{str(result.report.scan_id)[:8]}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/dataset", summary="Batch dataset analysis (JSON or CSV via format=)")
@limiter.limit("30/minute")
def analyze_integration_dataset(
    request: Request,
    payload: DatasetAnalysisRequest,
    format: str | None = None,
):
    """Analyze a batch of SaaS integrations. Use ?format=csv to export results as CSV."""
    rules = load_rules(use_cache=False)
    result = analyze_dataset(payload, rule_set=rules)
    if (format or "").lower() == "csv":
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow([
            "dataset_name", "integration_id", "risk_score", "risk_level",
            "oauth_over_permission", "token_misuse", "credential_exposure", "cross_platform_risk",
        ])
        for r in result.results:
            w.writerow([
                result.dataset_name,
                r.integration_id,
                r.risk_score,
                r.risk_level,
                r.oauth_over_permission_detected,
                r.token_misuse_detected,
                r.credential_exposure_detected,
                r.cross_platform_risk_detected,
            ])
        w.writerow([])
        w.writerow(["summary", "total_integrations", result.summary.total_integrations])
        w.writerow(["summary", "high_risk_integrations", result.summary.high_risk_integrations])
        w.writerow(["summary", "average_risk_score", result.summary.average_risk_score])
        buf.seek(0)
        return StreamingResponse(
            io.BytesIO(buf.getvalue().encode("utf-8-sig")),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=dataset_{result.dataset_name}.csv"},
        )
    return result
