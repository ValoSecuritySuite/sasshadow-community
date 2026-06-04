"""Compliance and governance mapping.

Maps scan findings to frameworks (SOC 2, ISO 27001, NIST AI RMF)
with control references, rationale, and remediation.
"""

from app.compliance.framework_mapper import (
    ComplianceMapping,
    FrameworkMapping,
    map_findings_to_frameworks,
)

__all__ = [
    "ComplianceMapping",
    "FrameworkMapping",
    "map_findings_to_frameworks",
]
