"""Aggregation layer for the basic SaaSShadow dashboard (Community Edition).

Reads the scan-history SQLite store and produces the DTOs declared in
:mod:`app.schemas_dashboard`. A small per-key TTL cache keeps repeat
calls cheap so a dashboard with multiple tiles does not hammer SQLite
on every refresh.

The functions in this module never raise on empty data: a fresh deploy
with zero scans returns zero-valued DTOs so the React layer always has
something to render.
"""

from __future__ import annotations

import json
import re
import sqlite3
import statistics
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

from app.core.config import settings
from app.core.logging import get_logger
from app.schemas_dashboard import (
    CriticalFindingEntry,
    CriticalFindingsResponse,
    DashboardOverview,
    RiskDistribution,
    RiskDistributionEntry,
    RiskTrendPoint,
    RiskTrendResponse,
    TrendBucket,
)

logger = get_logger(__name__)


_RISK_BAND = (
    (90.0, "CRITICAL"),
    (70.0, "HIGH"),
    (40.0, "MEDIUM"),
    (10.0, "LOW"),
)


def _risk_level_from_score(score: float) -> str:
    for floor, label in _RISK_BAND:
        if score >= floor:
            return label
    return "MINIMAL"


# ── TTL cache ───────────────────────────────────────────────────────────────


_cache_lock = threading.RLock()
_cache: dict[tuple[Any, ...], tuple[float, Any]] = {}


def _ttl() -> int:
    return int(getattr(settings, "dashboard_cache_ttl_seconds", 0) or 0)


def _cache_get(key: tuple[Any, ...]) -> Any:
    ttl = _ttl()
    if ttl <= 0:
        return None
    with _cache_lock:
        entry = _cache.get(key)
        if entry is None:
            return None
        stored_at, value = entry
        if time.monotonic() - stored_at > ttl:
            _cache.pop(key, None)
            return None
        return value


def _cache_set(key: tuple[Any, ...], value: Any) -> None:
    ttl = _ttl()
    if ttl <= 0:
        return
    with _cache_lock:
        _cache[key] = (time.monotonic(), value)


def clear_cache() -> None:
    """Drop every cached aggregator (used by tests and admin endpoints)."""
    with _cache_lock:
        _cache.clear()


def _cached(key: tuple[Any, ...], producer: Callable[[], Any]) -> Any:
    cached = _cache_get(key)
    if cached is not None:
        return cached
    value = producer()
    _cache_set(key, value)
    return value


# ── Window helpers ──────────────────────────────────────────────────────────


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _window_to_days(window: str | int | None, default: str | None = None) -> int:
    """Parse ``?window=`` query strings (``24h``, ``7d``, ``30d``, ``all``, ``42``)."""
    if window is None or window == "":
        window = default or settings.dashboard_default_window
    if isinstance(window, int):
        return max(int(window), 0)
    text = str(window).strip().lower()
    if text in {"all", "0"}:
        return 0
    match_h = re.match(r"^(\d+)\s*h(?:ours?)?$", text)
    if match_h:
        hours = max(int(match_h.group(1)), 0)
        return max(1, round(hours / 24)) if hours > 0 else 0
    match = re.match(r"^(\d+)\s*(d|day|days)?$", text)
    if match:
        return max(int(match.group(1)), 0)
    try:
        return max(int(text), 0)
    except ValueError:
        return 7


def _since_for_window(days: int) -> Optional[datetime]:
    if days <= 0:
        return None
    return _now() - timedelta(days=days)


# ── DB row helpers ──────────────────────────────────────────────────────────


def _connect_scan_history() -> sqlite3.Connection:
    path = settings.scan_history_db_path
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def _scans_in_range(since: Optional[datetime]) -> list[dict[str, Any]]:
    """Return scan rows with a parsed timestamp datetime."""
    query = "SELECT id, target, timestamp, score, risk_level, customer_id, key_findings FROM scans"
    params: list[Any] = []
    if since is not None:
        query += " WHERE timestamp >= ?"
        params.append(since.isoformat())
    query += " ORDER BY timestamp DESC"
    try:
        with _connect_scan_history() as conn:
            rows = conn.execute(query, params).fetchall()
    except sqlite3.OperationalError:
        return []
    out: list[dict[str, Any]] = []
    for r in rows:
        d = {k: r[k] for k in r.keys()}
        d["timestamp_dt"] = _parse_iso(d.get("timestamp"))
        try:
            d["key_findings_list"] = json.loads(d.get("key_findings") or "[]")
        except json.JSONDecodeError:
            d["key_findings_list"] = []
        out.append(d)
    return out


def _latest_per_target(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return the newest scan per (target, customer_id) tuple."""
    seen: dict[tuple[str, str], dict[str, Any]] = {}
    for r in rows:
        key = (r.get("target") or "", r.get("customer_id") or "")
        existing = seen.get(key)
        if existing is None:
            seen[key] = r
            continue
        if (r.get("timestamp_dt") or datetime.min.replace(tzinfo=timezone.utc)) > (
            existing.get("timestamp_dt") or datetime.min.replace(tzinfo=timezone.utc)
        ):
            seen[key] = r
    return list(seen.values())


# ── Overview ────────────────────────────────────────────────────────────────


def compute_overview(window_days: int) -> DashboardOverview:
    window_days = max(int(window_days), 0)
    key = ("overview", window_days)
    cached = _cache_get(key)
    if cached is not None:
        return cached

    all_rows = _scans_in_range(None)
    since = _since_for_window(window_days)
    in_window = (
        [r for r in all_rows if (r.get("timestamp_dt") or _now()) >= since]
        if since is not None
        else list(all_rows)
    )

    integrations_tracked = len({(r.get("target") or "", r.get("customer_id") or "") for r in all_rows})
    integrations_in_window = len(
        {(r.get("target") or "", r.get("customer_id") or "") for r in in_window}
    )

    latest = _latest_per_target(in_window)
    scores = [float(r.get("score") or 0.0) for r in latest]
    avg = float(sum(scores) / len(scores)) if scores else 0.0
    median = float(statistics.median(scores)) if scores else 0.0
    portfolio_level = _risk_level_from_score(avg)

    critical_integrations = sum(
        1 for r in latest if (r.get("risk_level") or "") in {"CRITICAL", "HIGH"}
    )

    # Period-over-period delta on avg risk score.
    delta = 0.0
    if since is not None and window_days > 0:
        prior_start = since - timedelta(days=window_days)
        prior = [
            r
            for r in all_rows
            if r.get("timestamp_dt") is not None
            and prior_start <= r["timestamp_dt"] < since
        ]
        prior_latest = _latest_per_target(prior)
        prior_scores = [float(r.get("score") or 0.0) for r in prior_latest]
        prior_avg = (
            float(sum(prior_scores) / len(prior_scores)) if prior_scores else 0.0
        )
        delta = round(avg - prior_avg, 2)

    overview = DashboardOverview(
        window_days=window_days,
        scans_total=len(all_rows),
        scans_in_window=len(in_window),
        integrations_tracked=integrations_tracked,
        integrations_in_window=integrations_in_window,
        avg_risk_score=round(avg, 2),
        median_risk_score=round(median, 2),
        portfolio_risk_level=portfolio_level,  # type: ignore[arg-type]
        critical_integrations=critical_integrations,
        risk_delta_vs_prior_window=delta,
    )
    _cache_set(key, overview)
    return overview


# ── Trend ───────────────────────────────────────────────────────────────────


_BUCKET_DELTAS: dict[TrendBucket, timedelta] = {
    "hour": timedelta(hours=1),
    "day": timedelta(days=1),
    "week": timedelta(weeks=1),
}


def _bucket_start(dt: datetime, bucket: TrendBucket) -> datetime:
    dt = dt.astimezone(timezone.utc)
    if bucket == "hour":
        return dt.replace(minute=0, second=0, microsecond=0)
    if bucket == "day":
        return dt.replace(hour=0, minute=0, second=0, microsecond=0)
    floor = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    return floor - timedelta(days=floor.weekday())


def compute_risk_trend(window_days: int, bucket: TrendBucket = "day") -> RiskTrendResponse:
    window_days = max(int(window_days), 0)
    key = ("trend", window_days, bucket)
    cached = _cache_get(key)
    if cached is not None:
        return cached

    since = _since_for_window(window_days)
    rows = _scans_in_range(since)

    buckets: dict[datetime, list[float]] = {}
    for r in rows:
        dt = r.get("timestamp_dt")
        if dt is None:
            continue
        b_start = _bucket_start(dt, bucket)
        buckets.setdefault(b_start, []).append(float(r.get("score") or 0.0))

    if since is not None and window_days > 0:
        cursor = _bucket_start(since, bucket)
        end = _bucket_start(_now(), bucket)
        step = _BUCKET_DELTAS[bucket]
        while cursor <= end:
            buckets.setdefault(cursor, [])
            cursor += step

    points: list[RiskTrendPoint] = []
    for start in sorted(buckets):
        scores = buckets[start]
        if scores:
            points.append(
                RiskTrendPoint(
                    bucket_start=start,
                    avg_risk_score=round(sum(scores) / len(scores), 2),
                    max_risk_score=round(max(scores), 2),
                    scans=len(scores),
                )
            )
        else:
            points.append(
                RiskTrendPoint(
                    bucket_start=start,
                    avg_risk_score=0.0,
                    max_risk_score=0.0,
                    scans=0,
                )
            )

    response = RiskTrendResponse(window_days=window_days, bucket=bucket, points=points)
    _cache_set(key, response)
    return response


# ── Distribution ────────────────────────────────────────────────────────────


def compute_risk_distribution() -> RiskDistribution:
    key = ("distribution",)
    cached = _cache_get(key)
    if cached is not None:
        return cached
    rows = _scans_in_range(None)
    latest = _latest_per_target(rows)
    counts: dict[str, int] = {level: 0 for level in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "MINIMAL")}
    for r in latest:
        level = r.get("risk_level") or _risk_level_from_score(
            float(r.get("score") or 0.0)
        )
        counts[level] = counts.get(level, 0) + 1
    entries = [
        RiskDistributionEntry(risk_level=level, count=count)  # type: ignore[arg-type]
        for level, count in counts.items()
    ]
    distribution = RiskDistribution(total_integrations=len(latest), entries=entries)
    _cache_set(key, distribution)
    return distribution


# ── Critical findings ───────────────────────────────────────────────────────


def compute_recent_critical(limit: int = 20) -> CriticalFindingsResponse:
    limit = max(1, int(limit))
    key = ("critical", limit)
    cached = _cache_get(key)
    if cached is not None:
        return cached

    rows = _scans_in_range(None)
    out: list[CriticalFindingEntry] = []
    for r in rows:
        score = float(r.get("score") or 0.0)
        level = r.get("risk_level") or _risk_level_from_score(score)
        findings = r.get("key_findings_list") or []
        if not findings and level in {"CRITICAL", "HIGH"}:
            # No granular findings persisted: still surface the scan itself.
            out.append(
                CriticalFindingEntry(
                    scan_id=str(r.get("id") or ""),
                    target=str(r.get("target") or ""),
                    customer_id=r.get("customer_id"),
                    created_at=r.get("timestamp_dt") or _now(),
                    risk_score=round(score, 2),
                    risk_level=level,  # type: ignore[arg-type]
                    rule_id=None,
                    category=None,
                    severity=4 if level == "HIGH" else 5,
                    summary=f"{level} risk scan on {r.get('target') or 'unknown target'}",
                )
            )
            if len(out) >= limit:
                break
            continue
        for finding in findings:
            severity = int(finding.get("severity") or 0)
            if severity < 4 and level not in {"CRITICAL", "HIGH"}:
                continue
            summary = (finding.get("evidence") or "").splitlines()[0:1]
            summary_text = summary[0] if summary else (finding.get("rule_id") or "")
            out.append(
                CriticalFindingEntry(
                    scan_id=str(r.get("id") or ""),
                    target=str(r.get("target") or ""),
                    customer_id=r.get("customer_id"),
                    created_at=r.get("timestamp_dt") or _now(),
                    risk_score=round(score, 2),
                    risk_level=level,  # type: ignore[arg-type]
                    rule_id=finding.get("rule_id"),
                    category=finding.get("category"),
                    severity=max(0, min(5, severity)),
                    summary=summary_text or "critical finding",
                )
            )
            if len(out) >= limit:
                break
        if len(out) >= limit:
            break

    response = CriticalFindingsResponse(limit=limit, findings=out[:limit])
    _cache_set(key, response)
    return response


__all__ = [
    "_window_to_days",
    "clear_cache",
    "compute_overview",
    "compute_recent_critical",
    "compute_risk_distribution",
    "compute_risk_trend",
]
