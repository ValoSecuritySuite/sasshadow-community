"""Usage plugin: track scans and API usage, expose stats and a human-readable summary.

Hooks:
    record_scan(target, score)     – record a scan for a target with risk score
    record_endpoint(path, method)  – record an API endpoint call
    get_usage_stats()              – return full stats dict (scans, endpoints)
    get_usage_summary()            – return a short human-readable summary string
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

# In-memory store (single process). For multi-process, use Redis or DB.
_SCANS: list[dict[str, Any]] = []
_ENDPOINT_CALLS: list[dict[str, Any]] = []

PLUGIN_NAME = "Usage"
PLUGIN_VERSION = "1.0.0"
PLUGIN_DESCRIPTION = (
    "Tracks scan and API endpoint usage in memory. Exposes stats and a "
    "human-readable summary for dashboards and docs."
)
PLUGIN_AUTHOR = "Core Platform Team"
PLUGIN_TAGS = ["usage", "telemetry", "stats", "dashboard"]


def _record_scan(target: str, score: float) -> None:
    """Record a single scan (target id and risk score)."""
    _SCANS.append({"target": target, "score": score})


def _record_endpoint(path: str, method: str) -> None:
    """Record an API endpoint invocation."""
    _ENDPOINT_CALLS.append({"path": path, "method": method})


def _get_usage_stats() -> dict[str, Any]:
    """Return full usage statistics (scans and endpoints)."""
    by_target: dict[str, int] = defaultdict(int)
    for s in _SCANS:
        by_target[s["target"]] += 1
    endpoint_counts: dict[str, int] = defaultdict(int)
    for e in _ENDPOINT_CALLS:
        key = f"{e['method']} {e['path']}"
        endpoint_counts[key] += 1
    return {
        "scans": {
            "total": len(_SCANS),
            "by_target": dict(by_target),
            "recent": _SCANS[-20:] if len(_SCANS) > 20 else list(_SCANS),
        },
        "endpoints": {
            "total_calls": len(_ENDPOINT_CALLS),
            "calls": _ENDPOINT_CALLS[-50:] if len(_ENDPOINT_CALLS) > 50 else list(_ENDPOINT_CALLS),
            "by_route": dict(endpoint_counts),
        },
    }


def _get_usage_summary() -> str:
    """Return a short human-readable usage summary."""
    stats = _get_usage_stats()
    total_scans = stats["scans"]["total"]
    total_calls = stats["endpoints"]["total_calls"]
    targets = list(stats["scans"]["by_target"].keys())
    top = targets[:5] if targets else []
    lines = [
        f"Total scans: {total_scans}",
        f"Total API calls: {total_calls}",
        f"Targets scanned: {len(targets)}",
    ]
    if top:
        lines.append(f"Sample targets: {', '.join(top)}")
    return " | ".join(lines)


def register() -> dict[str, Any]:
    """Plugin entry point."""
    return {
        "name": PLUGIN_NAME,
        "version": PLUGIN_VERSION,
        "description": PLUGIN_DESCRIPTION,
        "author": PLUGIN_AUTHOR,
        "tags": PLUGIN_TAGS,
        "enabled": True,
        "hooks": {
            "record_scan": _record_scan,
            "record_endpoint": _record_endpoint,
            "get_usage_stats": _get_usage_stats,
            "get_usage_summary": _get_usage_summary,
        },
    }
