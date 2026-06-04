"""JSON report module.

Delegates to ``services.report_generator`` — this module provides
a clean import path matching the target project structure.
"""

from app.services.report_generator import (  # noqa: F401
    build_report_from_pipeline,
    build_report_from_scan_input,
)
