"""PDF report module.

Delegates to ``services.pdf_report_generator`` — this module provides
a clean import path matching the target project structure.
"""

from app.services.pdf_report_generator import generate_executive_pdf  # noqa: F401
