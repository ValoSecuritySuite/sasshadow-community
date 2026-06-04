"""SQLite-backed scan history for dashboards and trends.

Stores each scan with target, timestamp, score, risk_level, optional customer_id,
and key findings (JSON). Used by GET /scans and GET /scans/{id}.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger
from app.models.scan_models import ScanReport

logger = get_logger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS scans (
    id TEXT PRIMARY KEY,
    target TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    score REAL NOT NULL,
    risk_level TEXT NOT NULL,
    customer_id TEXT,
    key_findings TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_scans_target ON scans(target);
CREATE INDEX IF NOT EXISTS idx_scans_timestamp ON scans(timestamp);
CREATE INDEX IF NOT EXISTS idx_scans_customer_id ON scans(customer_id);
"""


def _db_path() -> Path:
    path = settings.scan_history_db_path
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def init_scan_history_db() -> None:
    """Create the scans table and parent directory if needed."""
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(path)) as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Scan history DB initialized at %s", path)


def _key_findings_from_report(report: ScanReport) -> list[dict[str, Any]]:
    """Serialize report findings to a minimal list for storage (evidence truncated)."""
    out: list[dict[str, Any]] = []
    for f in report.findings:
        evidence = getattr(f, "evidence", "") or ""
        if len(evidence) > 500:
            evidence = evidence[:497] + "..."
        out.append({
            "rule_id": getattr(f, "rule_id", ""),
            "category": getattr(f, "category", ""),
            "severity": getattr(f, "severity", 0),
            "evidence": evidence,
        })
    return out


def insert_scan(
    report: ScanReport,
    target: str,
    *,
    customer_id: str | None = None,
) -> None:
    """Persist a scan report to the history database."""
    init_scan_history_db()
    key_findings = _key_findings_from_report(report)
    ts = report.timestamp
    if hasattr(ts, "isoformat"):
        ts_str = ts.isoformat()
    else:
        ts_str = str(ts)
    with sqlite3.connect(str(_db_path())) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO scans (id, target, timestamp, score, risk_level, customer_id, key_findings)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report.scan_id,
                target,
                ts_str,
                report.risk_score,
                report.risk_level,
                customer_id,
                json.dumps(key_findings),
            ),
        )
    logger.debug("Persisted scan %s target=%s", report.scan_id, target)


def get_scan_by_id(scan_id: str) -> dict[str, Any] | None:
    """Return a single scan by id, or None if not found."""
    init_scan_history_db()
    with sqlite3.connect(str(_db_path())) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM scans WHERE id = ?", (scan_id,)).fetchone()
    if row is None:
        return None
    r = dict(row)
    r["key_findings"] = json.loads(r["key_findings"])
    return r


def list_scans(
    *,
    target: str | None = None,
    customer_id: str | None = None,
    from_ts: datetime | str | None = None,
    to_ts: datetime | str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """List scans with optional filters. Returns list of dicts (no key_findings in list view)."""
    init_scan_history_db()
    query = "SELECT id, target, timestamp, score, risk_level, customer_id, key_findings FROM scans WHERE 1=1"
    params: list[Any] = []
    if target is not None and target != "":
        query += " AND target = ?"
        params.append(target)
    if customer_id is not None and customer_id != "":
        query += " AND customer_id = ?"
        params.append(customer_id)
    if from_ts is not None:
        from_str = from_ts.isoformat() if isinstance(from_ts, datetime) else str(from_ts)
        query += " AND timestamp >= ?"
        params.append(from_str)
    if to_ts is not None:
        to_str = to_ts.isoformat() if isinstance(to_ts, datetime) else str(to_ts)
        query += " AND timestamp <= ?"
        params.append(to_str)
    query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    with sqlite3.connect(str(_db_path())) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query, params).fetchall()
    out = []
    for row in rows:
        d = dict(row)
        # For list, include findings_count only; full key_findings only in get by id
        kf = json.loads(d["key_findings"])
        d["findings_count"] = len(kf)
        del d["key_findings"]
        out.append(d)
    return out


def get_latest_before(
    target: str,
    *,
    customer_id: str | None = None,
    exclude_scan_id: str | None = None,
) -> dict[str, Any] | None:
    """Return the most recent persisted scan for ``target`` strictly older than ``exclude_scan_id``.

    Includes the parsed ``key_findings`` list (suitable for the rescan
    diff worker). Returns None when no such scan exists.
    """
    init_scan_history_db()
    query = "SELECT * FROM scans WHERE target = ?"
    params: list[Any] = [target]
    if customer_id is not None and customer_id != "":
        query += " AND customer_id = ?"
        params.append(customer_id)
    if exclude_scan_id:
        query += " AND id <> ?"
        params.append(exclude_scan_id)
    query += " ORDER BY timestamp DESC, id DESC LIMIT 1"
    with sqlite3.connect(str(_db_path())) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(query, params).fetchone()
    if row is None:
        return None
    r = dict(row)
    try:
        r["key_findings"] = json.loads(r.get("key_findings") or "[]")
    except json.JSONDecodeError:
        r["key_findings"] = []
    return r


def get_last_two_scans_for_target(target: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Return (newer_scan, older_scan) for the given target, or (None, None) if fewer than 2.
    Both include key_findings. Order: newer = most recent, older = previous.
    """
    rows = list_scans(target=target, limit=2, offset=0)
    if len(rows) < 2:
        return None, None
    newer = get_scan_by_id(rows[0]["id"])
    older = get_scan_by_id(rows[1]["id"])
    return newer, older


def compare_findings(
    before_findings: list[dict[str, Any]],
    after_findings: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (new_findings, mitigated_findings). Match by (rule_id, category)."""
    def key(f: dict) -> tuple[str, str]:
        return (f.get("rule_id") or "", f.get("category") or "")
    before_set = {key(f): f for f in before_findings}
    after_set = {key(f): f for f in after_findings}
    new = [after_set[k] for k in after_set if k not in before_set]
    mitigated = [before_set[k] for k in before_set if k not in after_set]
    return new, mitigated
