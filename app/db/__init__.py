"""Persistence layer for SaaSShadow (scan history)."""

from app.db.scan_history import (
    compare_findings,
    get_last_two_scans_for_target,
    get_scan_by_id,
    init_scan_history_db,
    insert_scan,
    list_scans,
)

__all__ = [
    "compare_findings",
    "get_last_two_scans_for_target",
    "get_scan_by_id",
    "init_scan_history_db",
    "insert_scan",
    "list_scans",
]
