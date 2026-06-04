"""Scan history API — list, retrieve, compare, and export scans."""

import csv
import io

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.core.limiter import limiter
from app.db.scan_history import (
    compare_findings,
    get_last_two_scans_for_target,
    get_scan_by_id,
    list_scans,
)
from app.models.scan_models import (
    KeyFindingSummary,
    ScanCompareResponse,
    ScanDetail,
    ScanListItem,
    ScanListResponse,
)

router = APIRouter(prefix="/scans", tags=["Scan History"])


@router.get("", response_model=ScanListResponse, summary="List scan history")
@limiter.limit("100/minute")
def list_scan_history(
    request: Request,
    target: str | None = None,
    customer_id: str | None = None,
    from_ts: str | None = None,
    to_ts: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> ScanListResponse:
    """List persisted scans with optional filters.

    - **target**: exact match on integration target name
    - **customer_id**: filter by customer/tenant id
    - **from_ts**: only scans with timestamp >= this (ISO format)
    - **to_ts**: only scans with timestamp <= this (ISO format)
    - **limit**: max results (default 50)
    - **offset**: pagination offset (default 0)
    """
    if limit < 1:
        limit = 1
    if limit > 200:
        limit = 200
    if offset < 0:
        offset = 0
    rows = list_scans(
        target=target,
        customer_id=customer_id,
        from_ts=from_ts,
        to_ts=to_ts,
        limit=limit,
        offset=offset,
    )
    items = [
        ScanListItem(
            id=r["id"],
            target=r["target"],
            timestamp=r["timestamp"],
            score=r["score"],
            risk_level=r["risk_level"],
            customer_id=r.get("customer_id"),
            findings_count=r.get("findings_count", 0),
        )
        for r in rows
    ]
    return ScanListResponse(scans=items)


@router.get("/compare", response_model=ScanCompareResponse, summary="Compare two scans (trend/diff)")
@limiter.limit("60/minute")
def compare_scans(
    request: Request,
    target: str | None = None,
    before: str | None = None,
    after: str | None = None,
) -> ScanCompareResponse:
    """Compare two scans for the same target: score delta, new findings, mitigated findings.

    - **target** (required if before/after omitted): integration target name.
    - **before**: older scan id (optional).
    - **after**: newer scan id (optional).

    If only **target** is provided, the last two scans for that target are used
    (newest = after, previous = before). If **before** and **after** are provided,
    they must both exist and belong to the same target.
    """
    if before and after:
        scan_before = get_scan_by_id(before)
        scan_after = get_scan_by_id(after)
        if not scan_before:
            raise HTTPException(status_code=404, detail=f"Scan {before} not found")
        if not scan_after:
            raise HTTPException(status_code=404, detail=f"Scan {after} not found")
        if scan_before.get("target") != scan_after.get("target"):
            raise HTTPException(status_code=400, detail="before and after scans must have the same target")
        target_name = scan_before["target"]
    elif target:
        newer, older = get_last_two_scans_for_target(target)
        if not newer or not older:
            raise HTTPException(
                status_code=404,
                detail=f"Need at least two scans for target '{target}' to compare",
            )
        scan_after = newer
        scan_before = older
        target_name = target
    else:
        raise HTTPException(status_code=400, detail="Provide target= or both before= and after=")
    b_findings = scan_before.get("key_findings") or []
    a_findings = scan_after.get("key_findings") or []
    new_list, mitigated_list = compare_findings(b_findings, a_findings)
    score_before = float(scan_before["score"])
    score_after = float(scan_after["score"])
    return ScanCompareResponse(
        target=target_name,
        before_scan_id=scan_before["id"],
        after_scan_id=scan_after["id"],
        timestamp_before=scan_before["timestamp"],
        timestamp_after=scan_after["timestamp"],
        score_before=score_before,
        score_after=score_after,
        score_delta=round(score_after - score_before, 2),
        risk_level_before=scan_before.get("risk_level") or "",
        risk_level_after=scan_after.get("risk_level") or "",
        new_findings=[KeyFindingSummary(rule_id=f.get("rule_id", ""), category=f.get("category", ""), severity=f.get("severity", 0), evidence=f.get("evidence", "")) for f in new_list],
        mitigated_findings=[KeyFindingSummary(rule_id=f.get("rule_id", ""), category=f.get("category", ""), severity=f.get("severity", 0), evidence=f.get("evidence", "")) for f in mitigated_list],
    )


@router.get("/export", summary="Export scan list as CSV")
@limiter.limit("30/minute")
def export_scans_csv(
    request: Request,
    target: str | None = None,
    customer_id: str | None = None,
    from_ts: str | None = None,
    to_ts: str | None = None,
    limit: int = 1000,
) -> StreamingResponse:
    """Export scan history as CSV (for GRC, spreadsheets). Same filters as GET /scans."""
    if limit < 1:
        limit = 1
    if limit > 5000:
        limit = 5000
    rows = list_scans(target=target, customer_id=customer_id, from_ts=from_ts, to_ts=to_ts, limit=limit, offset=0)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "target", "timestamp", "score", "risk_level", "customer_id", "findings_count"])
    for r in rows:
        w.writerow([r.get("id"), r.get("target"), r.get("timestamp"), r.get("score"), r.get("risk_level"), r.get("customer_id") or "", r.get("findings_count", 0)])
    buf.seek(0)
    return StreamingResponse(
        io.BytesIO(buf.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=scans_export.csv"},
    )


@router.get("/{scan_id}/findings/export", summary="Export scan findings as CSV")
@limiter.limit("60/minute")
def export_scan_findings_csv(request: Request, scan_id: str) -> StreamingResponse:
    """Export key findings for one scan as CSV. Defined before /{scan_id} so path matches."""
    row = get_scan_by_id(scan_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Scan {scan_id} not found")
    findings = row.get("key_findings") or []
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["rule_id", "category", "severity", "evidence"])
    for f in findings:
        w.writerow([f.get("rule_id"), f.get("category"), f.get("severity"), (f.get("evidence") or "").replace("\r", " ").replace("\n", " ")])
    buf.seek(0)
    return StreamingResponse(
        io.BytesIO(buf.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=findings_{scan_id[:8]}.csv"},
    )


@router.get("/{scan_id}", response_model=ScanDetail, summary="Get scan by id")
@limiter.limit("100/minute")
def get_scan(
    request: Request,
    scan_id: str,
) -> ScanDetail:
    """Return a single persisted scan by id, including key findings. 404 if not found."""
    row = get_scan_by_id(scan_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Scan {scan_id} not found")
    key_findings = [
        KeyFindingSummary(
            rule_id=f.get("rule_id", ""),
            category=f.get("category", ""),
            severity=f.get("severity", 0),
            evidence=f.get("evidence", ""),
        )
        for f in row.get("key_findings", [])
    ]
    return ScanDetail(
        id=row["id"],
        target=row["target"],
        timestamp=row["timestamp"],
        score=row["score"],
        risk_level=row["risk_level"],
        customer_id=row.get("customer_id"),
        key_findings=key_findings,
    )
