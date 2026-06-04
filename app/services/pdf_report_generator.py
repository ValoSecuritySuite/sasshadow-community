"""Executive-grade PDF report generator.

Produces a fully structured, professional PDF from a :class:`ScanReport`
with dynamic content driven by the loaded YAML rule set.

Layout
------
Page 1  – Cover: title, scan metadata, risk-score badge
Page 2+ – Executive Summary
          Risk Score Breakdown
          Matched Rules
          Findings Table
          Recommendations
          Appendix: Rules Inventory
"""

from __future__ import annotations

import base64
import io
import re
from xml.sax.saxutils import escape
from datetime import datetime, timezone
from typing import Optional, Tuple

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    Image,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.flowables import Flowable

from app.core.exceptions import ServiceError
from app.core.logging import get_logger
from app.models.scan_models import ScanReport

logger = get_logger(__name__)

_DEFAULT_COMPANY_NAME = "SaaSShadow.ai"

# ── Palette ───────────────────────────────────────────────────────────────────
_NAVY       = colors.HexColor("#0F1F3D")
_BLUE       = colors.HexColor("#1E40AF")
_BLUE_LIGHT = colors.HexColor("#3B82F6")
_TEAL       = colors.HexColor("#0E7490")
_WHITE      = colors.white
_LIGHT_GRAY = colors.HexColor("#F1F5F9")
_MID_GRAY   = colors.HexColor("#CBD5E1")
_DARK_GRAY  = colors.HexColor("#334155")
_TEXT       = colors.HexColor("#1E293B")

# Severity colours
_SEV_COLORS = {
    1: colors.HexColor("#22C55E"),   # green    – Info
    2: colors.HexColor("#3B82F6"),   # blue     – Low
    3: colors.HexColor("#F59E0B"),   # amber    – Medium
    4: colors.HexColor("#EF4444"),   # red      – High
    5: colors.HexColor("#7F1D1D"),   # dark red – Critical
}
_SEV_LABELS = {1: "INFO", 2: "LOW", 3: "MEDIUM", 4: "HIGH", 5: "CRITICAL"}

# Risk-score bands
def _risk_color(score: float) -> colors.Color:
    if score >= 80:
        return colors.HexColor("#7F1D1D")
    if score >= 60:
        return colors.HexColor("#EF4444")
    if score >= 40:
        return colors.HexColor("#F59E0B")
    if score >= 20:
        return colors.HexColor("#3B82F6")
    return colors.HexColor("#22C55E")

def _risk_label(score: float) -> str:
    if score >= 80:
        return "CRITICAL"
    if score >= 60:
        return "HIGH"
    if score >= 40:
        return "MEDIUM"
    if score >= 20:
        return "LOW"
    return "MINIMAL"


# ── Styles ────────────────────────────────────────────────────────────────────
_BASE = getSampleStyleSheet()

def _make_styles() -> dict:
    return {
        "cover_title": ParagraphStyle(
            "cover_title",
            fontName="Helvetica-Bold",
            fontSize=28,
            textColor=_WHITE,
            leading=34,
            alignment=TA_LEFT,
        ),
        "cover_sub": ParagraphStyle(
            "cover_sub",
            fontName="Helvetica",
            fontSize=11,
            textColor=colors.HexColor("#93C5FD"),
            leading=16,
            alignment=TA_LEFT,
        ),
        "cover_meta": ParagraphStyle(
            "cover_meta",
            fontName="Helvetica",
            fontSize=9,
            textColor=colors.HexColor("#CBD5E1"),
            leading=14,
            alignment=TA_LEFT,
        ),
        "cover_company": ParagraphStyle(
            "cover_company",
            fontName="Helvetica-Bold",
            fontSize=12,
            textColor=_WHITE,
            leading=16,
            alignment=TA_LEFT,
        ),
        "h1": ParagraphStyle(
            "h1",
            fontName="Helvetica-Bold",
            fontSize=16,
            textColor=_NAVY,
            leading=22,
            spaceBefore=14,
            spaceAfter=4,
        ),
        "h2": ParagraphStyle(
            "h2",
            fontName="Helvetica-Bold",
            fontSize=12,
            textColor=_BLUE,
            leading=16,
            spaceBefore=10,
            spaceAfter=2,
        ),
        "body": ParagraphStyle(
            "body",
            fontName="Helvetica",
            fontSize=9.5,
            textColor=_TEXT,
            leading=14,
            spaceAfter=4,
        ),
        "body_sm": ParagraphStyle(
            "body_sm",
            fontName="Helvetica",
            fontSize=8.5,
            textColor=_DARK_GRAY,
            leading=12,
        ),
        "code": ParagraphStyle(
            "code",
            fontName="Courier",
            fontSize=8,
            textColor=_DARK_GRAY,
            leading=11,
            backColor=_LIGHT_GRAY,
            leftIndent=6,
            rightIndent=6,
        ),
        "badge_label": ParagraphStyle(
            "badge_label",
            fontName="Helvetica-Bold",
            fontSize=8,
            textColor=_WHITE,
            alignment=TA_CENTER,
            leading=10,
        ),
        "footer": ParagraphStyle(
            "footer",
            fontName="Helvetica",
            fontSize=7.5,
            textColor=colors.HexColor("#94A3B8"),
            alignment=TA_CENTER,
        ),
        "tbl_header": ParagraphStyle(
            "tbl_header",
            fontName="Helvetica-Bold",
            fontSize=8.5,
            textColor=_WHITE,
            alignment=TA_CENTER,
        ),
        "tbl_cell": ParagraphStyle(
            "tbl_cell",
            fontName="Helvetica",
            fontSize=8,
            textColor=_TEXT,
            leading=11,
        ),
        "tbl_cell_center": ParagraphStyle(
            "tbl_cell_center",
            fontName="Helvetica",
            fontSize=8,
            textColor=_TEXT,
            alignment=TA_CENTER,
            leading=11,
        ),
        "metric_value": ParagraphStyle(
            "metric_value",
            fontName="Helvetica-Bold",
            fontSize=22,
            textColor=_NAVY,
            alignment=TA_CENTER,
            leading=26,
        ),
        "metric_label": ParagraphStyle(
            "metric_label",
            fontName="Helvetica",
            fontSize=8,
            textColor=_DARK_GRAY,
            alignment=TA_CENTER,
            leading=11,
        ),
        "recommend_title": ParagraphStyle(
            "recommend_title",
            fontName="Helvetica-Bold",
            fontSize=9.5,
            textColor=_NAVY,
            leading=14,
            spaceBefore=4,
        ),
        "recommend_body": ParagraphStyle(
            "recommend_body",
            fontName="Helvetica",
            fontSize=9,
            textColor=_TEXT,
            leading=13,
            leftIndent=12,
            spaceAfter=6,
        ),
    }


# ── Custom Flowables ──────────────────────────────────────────────────────────

class _ColorRect(Flowable):
    """A filled rounded-corner rectangle used as a coloured banner or badge."""

    def __init__(self, width: float, height: float, fill: colors.Color,
                 radius: float = 4, stroke_color: colors.Color | None = None):
        super().__init__()
        self.width = width
        self.height = height
        self._fill = fill
        self._radius = radius
        self._stroke = stroke_color

    def draw(self) -> None:
        c = self.canv
        c.saveState()
        c.setFillColor(self._fill)
        if self._stroke:
            c.setStrokeColor(self._stroke)
            c.setLineWidth(0.5)
        else:
            c.setStrokeColor(self._fill)
        c.roundRect(0, 0, self.width, self.height, self._radius, fill=1,
                    stroke=1 if self._stroke else 0)
        c.restoreState()


class _RiskGauge(Flowable):
    """Horizontal segmented risk gauge (0-100) with a marker at *score*."""

    def __init__(self, score: float, width: float = 300, height: float = 18):
        super().__init__()
        self.score = score
        self.width = width
        self.height = height

    def draw(self) -> None:
        c = self.canv
        c.saveState()
        segments = [
            (0, 20,  colors.HexColor("#22C55E")),
            (20, 40, colors.HexColor("#3B82F6")),
            (40, 60, colors.HexColor("#F59E0B")),
            (60, 80, colors.HexColor("#EF4444")),
            (80, 100, colors.HexColor("#7F1D1D")),
        ]
        seg_w = self.width / 5
        for i, (lo, hi, col) in enumerate(segments):
            c.setFillColor(col)
            c.setStrokeColor(_WHITE)
            c.setLineWidth(1)
            c.roundRect(i * seg_w, 0, seg_w, self.height, 2, fill=1, stroke=1)

        # Marker line – kept strictly within the flowable bounds so it isn't clipped
        marker_x = (self.score / 100.0) * self.width
        marker_x = max(3, min(self.width - 3, marker_x))
        c.setFillColor(_NAVY)
        c.setStrokeColor(_NAVY)
        c.setLineWidth(2.5)
        c.line(marker_x, 1, marker_x, self.height - 1)
        c.restoreState()


class _DefaultLogo(Flowable):
    """Simple placeholder logo when no custom logo is provided."""

    def __init__(self, size: float = 14 * mm):
        super().__init__()
        self.size = size

    def draw(self) -> None:
        c = self.canv
        c.saveState()
        c.setFillColor(_BLUE)
        c.roundRect(0, 0, self.size, self.size, 2, fill=1, stroke=0)
        c.setFillColor(_WHITE)
        c.setFont("Helvetica-Bold", 10)
        c.drawCentredString(self.size / 2, self.size / 2 - 3, "S")
        c.restoreState()


# ── Canvas callbacks (header / footer) ───────────────────────────────────────

def _make_page_cb(scan_id: str, timestamp: str, report_title: str):
    """Return a canvas callback that draws a branded header + footer."""

    def _draw(canvas, doc):  # noqa: ANN001
        w, h = A4
        canvas.saveState()

        # ── Explicit white page background (cover page handles its own) ──────
        canvas.setFillColor(colors.white)
        canvas.rect(0, 0, w, h, fill=1, stroke=0)

        # ── Header bar ──────────────────────────────────────────────────────
        canvas.setFillColor(_NAVY)
        canvas.rect(0, h - 28 * mm, w, 28 * mm, fill=1, stroke=0)

        canvas.setFillColor(_BLUE_LIGHT)
        canvas.rect(0, h - 30 * mm, w, 2 * mm, fill=1, stroke=0)

        canvas.setFont("Helvetica-Bold", 11)
        canvas.setFillColor(_WHITE)
        canvas.drawString(18 * mm, h - 16 * mm, report_title)

        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#93C5FD"))
        canvas.drawRightString(w - 18 * mm, h - 12 * mm, f"Scan ID: {scan_id}")
        canvas.drawRightString(w - 18 * mm, h - 18 * mm, timestamp)

        # ── Footer bar ───────────────────────────────────────────────────────
        canvas.setFillColor(_LIGHT_GRAY)
        canvas.rect(0, 0, w, 14 * mm, fill=1, stroke=0)

        canvas.setStrokeColor(_MID_GRAY)
        canvas.setLineWidth(0.5)
        canvas.line(18 * mm, 14 * mm, w - 18 * mm, 14 * mm)

        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#64748B"))
        canvas.drawString(18 * mm, 5 * mm, "CONFIDENTIAL – Security Scan Report")
        canvas.drawRightString(w - 18 * mm, 5 * mm,
                               f"Page {doc.page}")

        canvas.restoreState()

    return _draw


def _make_cover_cb(scan_id: str, timestamp: str):
    """Canvas callback for the cover page — full-bleed navy background."""

    def _draw(canvas, doc):  # noqa: ANN001
        w, h = A4
        canvas.saveState()

        # Full background
        canvas.setFillColor(_NAVY)
        canvas.rect(0, 0, w, h, fill=1, stroke=0)

        # Accent stripe
        canvas.setFillColor(_BLUE_LIGHT)
        canvas.rect(0, h * 0.42, w, 3, fill=1, stroke=0)

        # Bottom footer
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#475569"))
        canvas.drawString(18 * mm, 10 * mm, "CONFIDENTIAL – Security Scan Report")
        canvas.drawRightString(w - 18 * mm, 10 * mm,
                               f"Generated: {timestamp}  |  Scan ID: {scan_id}")

        canvas.restoreState()

    return _draw


def _decode_logo_bytes(raw: str) -> Optional[bytes]:
    value = raw.strip()
    if value.startswith("data:"):
        match = re.match(r"^data:[^;]+;base64,(.+)$", value, re.DOTALL)
        if not match:
            return None
        value = match.group(1)
    try:
        return base64.b64decode(value, validate=True)
    except Exception:
        return None


def _extract_branding(report: ScanReport) -> Tuple[Optional[str], Optional[bytes]]:
    """Community Edition uses the fixed product identity; custom branding
    (tenant company name / logo) is an Enterprise feature."""
    return _DEFAULT_COMPANY_NAME, None


def _scale_to_fit(width: float, height: float, max_w: float, max_h: float) -> tuple[float, float]:
    if width <= 0 or height <= 0:
        return max_w, max_h
    scale = min(max_w / width, max_h / height, 1.0)
    return width * scale, height * scale


def _build_logo_flowable(logo_bytes: bytes, max_w: float, max_h: float) -> Image:
    reader = ImageReader(io.BytesIO(logo_bytes))
    w_px, h_px = reader.getSize()
    draw_w, draw_h = _scale_to_fit(float(w_px), float(h_px), max_w, max_h)
    return Image(io.BytesIO(logo_bytes), width=draw_w, height=draw_h)


# ── Section builders ──────────────────────────────────────────────────────────

def _cover_section(report: ScanReport, st: dict, company_name: Optional[str], logo: Optional[Image]) -> list:
    """Build cover-page flowables (placed on the navy background)."""
    score_col = _risk_color(report.risk_score)
    risk_label = _risk_label(report.risk_score)
    target = report.metadata.get("target", "—")
    input_kind = report.metadata.get("input_kind", "—")
    ts = report.timestamp.strftime("%Y-%m-%d %H:%M UTC") if report.timestamp else "—"

    story: list = []
    if logo or company_name:
        story.append(Spacer(1, 16 * mm))
        if logo:
            story.append(logo)
            story.append(Spacer(1, 2 * mm))
        if company_name:
            story.append(Paragraph(f"Prepared for {escape(company_name)}", st["cover_company"]))
        story.append(Spacer(1, 24 * mm))
    else:
        story.append(Spacer(1, 68 * mm))

    # Product branding
    brand_name = escape(company_name) if company_name else _DEFAULT_COMPANY_NAME
    story.append(Paragraph(
        f'<font color="#3B82F6">■</font>  <font color="#93C5FD">{brand_name}</font>',
        ParagraphStyle("brand", fontName="Helvetica-Bold", fontSize=11,
                       textColor=colors.HexColor("#93C5FD"), leading=14),
    ))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph("SaaS Integration Risk Report", st["cover_title"]))
    story.append(Paragraph("OAuth, Token, Credential & Data Flow Analysis", st["cover_sub"]))
    story.append(Spacer(1, 10 * mm))

    # Divider
    story.append(HRFlowable(width="100%", thickness=0.5,
                             color=colors.HexColor("#1E3A5F"), spaceAfter=8))

    # Metadata row
    meta_data = [
        [
            Paragraph(f'<b><font color="#93C5FD">Target</font></b><br/>'
                      f'<font color="#E2E8F0">{target}</font>', st["cover_meta"]),
            Paragraph(f'<b><font color="#93C5FD">Input Kind</font></b><br/>'
                      f'<font color="#E2E8F0">{input_kind.upper()}</font>', st["cover_meta"]),
            Paragraph(f'<b><font color="#93C5FD">Scan Date</font></b><br/>'
                      f'<font color="#E2E8F0">{ts}</font>', st["cover_meta"]),
        ]
    ]
    meta_tbl = Table(meta_data, colWidths=["33%", "33%", "34%"])
    meta_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(meta_tbl)
    story.append(Spacer(1, 12 * mm))

    # Big risk-score badge
    badge_data = [[
        Paragraph(
            f'<font size="36"><b>{report.risk_score:.1f}</b></font><br/>'
            f'<font size="12"> / 100</font>',
            ParagraphStyle("rs_num", fontName="Helvetica-Bold", fontSize=36,
                           textColor=_WHITE, alignment=TA_CENTER, leading=42),
        ),
        Paragraph(
            f'<b><font size="18">{risk_label}</font></b><br/>'
            f'<font color="#CBD5E1" size="9">Combined Risk Score</font>',
            ParagraphStyle("rs_lbl", fontName="Helvetica-Bold", fontSize=18,
                           textColor=_WHITE, leading=24),
        ),
    ]]
    badge_tbl = Table(badge_data, colWidths=[50 * mm, 100 * mm])
    badge_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), score_col),
        ("ROUNDEDCORNERS", [6]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 14),
        ("RIGHTPADDING", (0, 0), (-1, -1), 14),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(badge_tbl)
    story.append(NextPageTemplate("body"))
    story.append(PageBreak())
    return story


def _executive_summary(report: ScanReport, st: dict) -> list:
    story: list = []
    story.append(Paragraph("Executive Summary", st["h1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=_BLUE_LIGHT, spaceAfter=6))

    target      = report.metadata.get("target", "—")
    input_kind  = report.metadata.get("input_kind", "—")
    content_len = report.metadata.get("content_length", "—")
    det_flags   = report.metadata.get("detection_flags", [])
    ts          = report.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC") if report.timestamp else "—"
    risk_label  = _risk_label(report.risk_score)
    risk_col    = _risk_color(report.risk_score)
    sev_label   = _SEV_LABELS.get(report.max_severity_found, "NONE")
    sev_col     = _SEV_COLORS.get(report.max_severity_found, _MID_GRAY)

    if report.executive_summary and isinstance(report.executive_summary, dict):
        narrative = report.executive_summary.get("narrative")
        if narrative:
            story.append(Paragraph(escape(str(narrative)), st["body"]))
        metrics = report.executive_summary.get("metrics") or {}
        if metrics:
            story.append(Spacer(1, 3 * mm))
            story.append(Paragraph("Key metrics", st["h2"]))
            for k, v in list(metrics.items())[:8]:
                story.append(Paragraph(f"<b>{k}</b>: {v}", st["body_sm"]))
    else:
        intro = (
            f"This report presents the results of a SaaS-to-SaaS integration risk analysis "
            f"performed on <b>{target}</b> at <b>{ts}</b>. SaaSShadow.ai evaluated the "
            f"integration configuration across four risk dimensions: <b>OAuth scope "
            f"over-permission</b>, <b>API token misuse</b>, <b>credential exposure</b>, "
            f"and <b>cross-platform data flow risk</b>. The composite risk score and "
            f"recommendations below are derived from the active YAML policy rules and "
            f"heuristic analyzers."
        )
        story.append(Paragraph(intro, st["body"]))
    story.append(Spacer(1, 5 * mm))

    # ── Key metrics row ──────────────────────────────────────────────────────
    metrics = [
        (f"{report.risk_score:.1f}", "Combined Risk Score", risk_col),
        (risk_label, "Risk Level", risk_col),
        (sev_label, "Max Severity", sev_col),
        (str(len(report.findings)), "Total Findings", _BLUE),
        (str(len(report.matched_rules)), "Matched Rules", _TEAL),
    ]

    metric_cells = []
    for val, lbl, col in metrics:
        cell = [
            Paragraph(f'<font color="{col.hexval()}" size="18"><b>{val}</b></font>',
                      st["metric_value"]),
            Paragraph(lbl, st["metric_label"]),
        ]
        metric_cells.append(cell)

    # Build 5-column metrics table
    row_vals  = [[Paragraph(f'<font size="18"><b>{v}</b></font>',
                             ParagraphStyle("mv2", fontName="Helvetica-Bold", fontSize=18,
                                             textColor=c, alignment=TA_CENTER, leading=22))
                  for v, _, c in metrics]]
    row_labels = [[Paragraph(l, st["metric_label"]) for _, l, _ in metrics]]

    col_w = [38 * mm] * 5
    mt = Table(row_vals + row_labels, colWidths=col_w)
    mt.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _LIGHT_GRAY),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [_LIGHT_GRAY, _WHITE]),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, 0), 10),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 4),
        ("TOPPADDING", (0, 1), (-1, 1), 2),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 10),
        ("BOX", (0, 0), (-1, -1), 0.5, _MID_GRAY),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, _MID_GRAY),
        ("ROUNDEDCORNERS", [4]),
    ]))
    story.append(mt)
    story.append(Spacer(1, 5 * mm))

    # Detection flags
    if det_flags:
        story.append(Paragraph("Detection Signals", st["h2"]))
        flags_str = "  ·  ".join(f'<font color="#1E40AF"><b>{f}</b></font>'
                                 for f in det_flags)
        story.append(Paragraph(flags_str, st["body_sm"]))

    # Scan metadata mini-table
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph("Scan Metadata", st["h2"]))
    meta_rows = [
        [Paragraph("<b>Scan ID</b>", st["tbl_cell"]),      Paragraph(str(report.scan_id),  st["tbl_cell"])],
        [Paragraph("<b>Target</b>", st["tbl_cell"]),        Paragraph(target,               st["tbl_cell"])],
        [Paragraph("<b>Input Kind</b>", st["tbl_cell"]),    Paragraph(input_kind.upper(),   st["tbl_cell"])],
        [Paragraph("<b>Content Length</b>", st["tbl_cell"]), Paragraph(f"{content_len} chars", st["tbl_cell"])],
        [Paragraph("<b>Timestamp</b>", st["tbl_cell"]),     Paragraph(ts,                  st["tbl_cell"])],
        [Paragraph("<b>Severity Ceiling</b>", st["tbl_cell"]),
         Paragraph("Applied" if report.severity_ceiling_applied else "Not applied", st["tbl_cell"])],
    ]
    meta_tbl = Table(meta_rows, colWidths=[52 * mm, 120 * mm])
    meta_tbl.setStyle(TableStyle([
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [_LIGHT_GRAY, _WHITE]),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("BOX", (0, 0), (-1, -1), 0.5, _MID_GRAY),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, _MID_GRAY),
    ]))
    story.append(meta_tbl)
    return story


def _analyzed_input_overview_section(report: ScanReport, st: dict) -> list:
    """ANALYZED INPUT OVERVIEW — target, source/destination, auth, format, sanitized preview."""
    story: list = []
    ov = getattr(report, "analyzed_input_overview", None)
    if not ov or not isinstance(ov, dict):
        return story
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph("Analyzed Input Overview", st["h1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=_BLUE_LIGHT, spaceAfter=6))
    rows = [
        ["Target Integration", ov.get("target_integration", "—")],
        ["Source System", ov.get("source_system", "—")],
        ["Destination System", ov.get("destination_system", "—")],
        ["Integration Description", str(ov.get("integration_description", "—"))[:80]],
        ["Authentication Type", ov.get("authentication_type", "—")],
        ["Input Format", ov.get("input_format", "—")],
        ["Content Length", f"{ov.get('content_length', 0)} characters"],
        ["Line Count", str(ov.get("line_count", 0))],
        ["Token Count", str(ov.get("token_count", 0))],
        ["Encoding", ov.get("encoding", "—")],
        ["Environment", ov.get("environment", "—")],
    ]
    tbl_data = [[Paragraph(escape(r[0]), st["tbl_cell"]), Paragraph(escape(str(r[1])), st["tbl_cell"])] for r in rows]
    tbl = Table(tbl_data, colWidths=[52 * mm, 125 * mm])
    tbl.setStyle(TableStyle([
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [_LIGHT_GRAY, _WHITE]),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("BOX", (0, 0), (-1, -1), 0.5, _MID_GRAY),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, _MID_GRAY),
    ]))
    story.append(tbl)
    preview = ov.get("input_preview", "")
    if preview:
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph("Input Preview", st["h2"]))
        safe_preview = "<br/>".join(escape(line) for line in (preview[:1500].splitlines()[:20]))
        story.append(Paragraph(f'<font face="Courier" size="7">{safe_preview}</font>', st["code"]))
    return story


def _integration_metadata_section(report: ScanReport, st: dict) -> list:
    """INTEGRATION METADATA — source/dest app, purpose, provider, data types, token rotation."""
    story: list = []
    meta = getattr(report, "integration_metadata", None)
    if not meta or not isinstance(meta, dict):
        return story
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph("Integration Metadata", st["h1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=_BLUE_LIGHT, spaceAfter=6))
    rows = [
        ["Source Application", meta.get("source_application", "—")],
        ["Destination Application", meta.get("destination_application", "—")],
        ["Integration Purpose", str(meta.get("integration_purpose", "—"))[:70]],
        ["Authentication Provider", meta.get("authentication_provider", "—")],
        ["OAuth Provider", meta.get("oauth_provider", "—")],
        ["Data Types", ", ".join(meta.get("detected_data_types") or []) or "—"],
        ["Integration Environment", meta.get("integration_environment", "—")],
        ["Credential Expiry", str(meta.get("credential_expiry_settings", "—"))],
        ["Token Rotation Enabled", "Yes" if meta.get("token_rotation_enabled") else "No"],
        ["Shared Token Across Integrations", "Yes" if meta.get("shared_token_across_integrations") else "No"],
    ]
    if meta.get("user_count") is not None:
        rows.append(["User Count (usage context)", str(meta["user_count"])])
    if meta.get("last_used") is not None:
        rows.append(["Last Used", str(meta["last_used"])])
    if meta.get("last_updated") is not None:
        rows.append(["Last Updated", str(meta["last_updated"])])
    tbl_data = [[Paragraph(escape(r[0]), st["tbl_cell"]), Paragraph(escape(str(r[1])), st["tbl_cell"])] for r in rows]
    tbl = Table(tbl_data, colWidths=[55 * mm, 122 * mm])
    tbl.setStyle(TableStyle([
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [_LIGHT_GRAY, _WHITE]),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("BOX", (0, 0), (-1, -1), 0.5, _MID_GRAY),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, _MID_GRAY),
    ]))
    story.append(tbl)
    return story


def _detection_signals_section(report: ScanReport, st: dict) -> list:
    """DETECTION SIGNALS — list of signals with brief explanation."""
    story: list = []
    sigs = getattr(report, "detection_signals", None)
    if not sigs or not isinstance(sigs, dict):
        return story
    signals_list = sigs.get("signals", [])
    if not signals_list:
        return story
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph("Detection Signals", st["h1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=_BLUE_LIGHT, spaceAfter=6))
    story.append(Paragraph("Signals discovered during scanning:", st["body"]))
    story.append(Spacer(1, 3 * mm))
    rows = [[Paragraph("Signal", st["tbl_header"]), Paragraph("Description", st["tbl_header"])]]
    for s in signals_list[:15]:
        if isinstance(s, dict):
            rows.append([
                Paragraph(escape(str(s.get("signal", "—"))), st["tbl_cell"]),
                Paragraph(escape(str(s.get("description", "—"))[:90]), st["tbl_cell"]),
            ])
    if len(rows) > 1:
        tbl = Table(rows, colWidths=[50 * mm, 127 * mm], repeatRows=1)
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), _BLUE),
            ("TEXTCOLOR", (0, 0), (-1, 0), _WHITE),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [_LIGHT_GRAY, _WHITE]),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("BOX", (0, 0), (-1, -1), 0.5, _MID_GRAY),
            ("INNERGRID", (0, 0), (-1, -1), 0.3, _MID_GRAY),
        ]))
        story.append(tbl)
    return story


def _integration_visibility_section(report: ScanReport, st: dict) -> list:
    """SaaS Integration Visibility — systems, links (Source | Target | Type | Direction | Data Types)."""
    story: list = []
    summary = getattr(report, "integration_visibility_summary", None)
    if not summary or not isinstance(summary, dict):
        return story
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph("Integration Visibility Summary", st["h1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=_BLUE_LIGHT, spaceAfter=6))
    systems = summary.get("systems", [])
    links_count = summary.get("links_count", 0)
    story.append(Paragraph(
        f"Discovered <b>{len(systems)}</b> system(s) and <b>{links_count}</b> connection(s). "
        f"OAuth-based links: {summary.get('has_oauth', False)}; API-based: {summary.get('has_api', False)}.",
        st["body"],
    ))
    if systems:
        story.append(Paragraph("Systems: " + ", ".join(escape(s) for s in systems[:15]), st["body_sm"]))
    links = summary.get("links", [])[:10]
    if links:
        story.append(Spacer(1, 3 * mm))
        story.append(Paragraph("Connections", st["h2"]))
        rows = [[Paragraph("Source", st["tbl_header"]), Paragraph("Target", st["tbl_header"]), Paragraph("Type", st["tbl_header"])]]
        for link in links:
            if isinstance(link, dict):
                rows.append([
                    Paragraph(escape(link.get("source", "—")), st["tbl_cell"]),
                    Paragraph(escape(link.get("target", "—")), st["tbl_cell"]),
                    Paragraph(escape(link.get("link_type", "—")), st["tbl_cell"]),
                ])
        if len(rows) > 1:
            tbl = Table(rows, colWidths=[55 * mm, 55 * mm, 67 * mm], repeatRows=1)
            tbl.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), _BLUE),
                ("TEXTCOLOR", (0, 0), (-1, 0), _WHITE),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [_LIGHT_GRAY, _WHITE]),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("BOX", (0, 0), (-1, -1), 0.5, _MID_GRAY),
                ("INNERGRID", (0, 0), (-1, -1), 0.3, _MID_GRAY),
            ]))
            story.append(tbl)
    return story


def _top_risky_connections_section(report: ScanReport, st: dict) -> list:
    """Top risky SaaS connections."""
    story: list = []
    connections = getattr(report, "top_risky_connections", None) or []
    if not connections or not isinstance(connections, list):
        return story
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph("Top Risky SaaS Connections", st["h1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=_BLUE_LIGHT, spaceAfter=6))
    rows = [[Paragraph("Source", st["tbl_header"]), Paragraph("Target", st["tbl_header"]), Paragraph("Risk Score", st["tbl_header"]), Paragraph("Type", st["tbl_header"])]]
    for c in connections[:10]:
        if isinstance(c, dict):
            src = c.get("source") or c.get("integration_id") or "—"
            tgt = c.get("target") or "—"
            score = c.get("risk_score", 0)
            typ = c.get("connection_type", "—")
            rows.append([
                Paragraph(escape(str(src)), st["tbl_cell"]),
                Paragraph(escape(str(tgt)), st["tbl_cell"]),
                Paragraph(f"<b>{score:.1f}</b>", st["tbl_cell_center"]),
                Paragraph(escape(str(typ)), st["tbl_cell"]),
            ])
    if len(rows) > 1:
        tbl = Table(rows, colWidths=[45 * mm, 45 * mm, 35 * mm, 52 * mm], repeatRows=1)
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), _NAVY),
            ("TEXTCOLOR", (0, 0), (-1, 0), _WHITE),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [_LIGHT_GRAY, _WHITE]),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("BOX", (0, 0), (-1, -1), 0.5, _MID_GRAY),
            ("INNERGRID", (0, 0), (-1, -1), 0.3, _MID_GRAY),
        ]))
        story.append(tbl)
    return story


def _ai_data_flow_risks_section(report: ScanReport, st: dict) -> list:
    """AI-related data flow risks."""
    story: list = []
    ai_risks = getattr(report, "ai_data_flow_risks", None)
    if not ai_risks or not isinstance(ai_risks, dict):
        return story
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph("AI-Related Data Flow Risks", st["h1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=_BLUE_LIGHT, spaceAfter=6))
    story.append(Paragraph(
        f"AI risk detected: <b>{ai_risks.get('ai_risk_detected', False)}</b>. "
        f"Findings: <b>{ai_risks.get('ai_findings_count', 0)}</b>. "
        f"AI risk score: <b>{ai_risks.get('ai_risk_score', 0):.1f}</b>. "
        f"Shadow AI: <b>{ai_risks.get('shadow_ai_detected', False)}</b>. "
        f"Enterprise data to AI: <b>{ai_risks.get('enterprise_data_to_ai', False)}</b>.",
        st["body"],
    ))
    hint = ai_risks.get("remediation_hint")
    if hint:
        story.append(Spacer(1, 2 * mm))
        story.append(Paragraph(f"<b>Recommendation:</b> {escape(hint)}", st["body_sm"]))
    return story


def _compliance_mapping_section(report: ScanReport, st: dict) -> list:
    """Compliance mapping (SOC 2, ISO 27001, NIST AI RMF)."""
    story: list = []
    mapping = getattr(report, "compliance_mapping", None) or []
    if not mapping or not isinstance(mapping, list):
        return story
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph("Compliance Mapping", st["h1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=_BLUE_LIGHT, spaceAfter=6))
    story.append(Paragraph(
        "Findings mapped to governance frameworks (SOC 2, ISO 27001, NIST AI RMF) with control references and remediation.",
        st["body"],
    ))
    story.append(Spacer(1, 3 * mm))
    rows = [[Paragraph("Finding", st["tbl_header"]), Paragraph("Framework", st["tbl_header"]), Paragraph("Control", st["tbl_header"]), Paragraph("Remediation", st["tbl_header"])]]
    for m in mapping[:15]:
        if isinstance(m, dict):
            rows.append([
                Paragraph(escape(str(m.get("finding_type", "—"))[:30]), st["tbl_cell"]),
                Paragraph(escape(str(m.get("framework", "—"))), st["tbl_cell_center"]),
                Paragraph(escape(str(m.get("control_reference", "—"))), st["tbl_cell_center"]),
                Paragraph(escape(str(m.get("recommended_remediation", "—"))[:80]), st["tbl_cell"]),
            ])
    if len(rows) > 1:
        tbl = Table(rows, colWidths=[38 * mm, 28 * mm, 28 * mm, 83 * mm], repeatRows=1)
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), _TEAL),
            ("TEXTCOLOR", (0, 0), (-1, 0), _WHITE),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [_LIGHT_GRAY, _WHITE]),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("BOX", (0, 0), (-1, -1), 0.5, _MID_GRAY),
            ("INNERGRID", (0, 0), (-1, -1), 0.3, _MID_GRAY),
        ]))
        story.append(tbl)
    return story


def _analyzer_breakdown_section(report: ScanReport, st: dict) -> list:
    """Analyzer Results Breakdown — OAuth, Token, Credential, Data Flow."""
    story: list = []
    br = getattr(report, "analyzer_breakdown", None)
    if not br or not isinstance(br, dict):
        return story
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph("Analyzer Results Breakdown", st["h1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=_BLUE_LIGHT, spaceAfter=6))

    oauth = br.get("oauth_scope_analysis") or {}
    story.append(Paragraph("OAuth Scope Analysis", st["h2"]))
    story.append(Paragraph(
        f"Total scopes: <b>{oauth.get('total_scopes_detected', 0)}</b>. "
        f"High risk: {len(oauth.get('high_risk_scopes') or [])}. "
        f"Wildcard: {len(oauth.get('wildcard_scopes') or [])}. "
        f"Over-permissioned: <b>{oauth.get('over_permissioned', False)}</b>. "
        f"Scope risk score: <b>{oauth.get('scope_risk_score', 0):.1f}</b>.",
        st["body_sm"],
    ))
    if oauth.get("scopes"):
        story.append(Paragraph("Scopes: " + ", ".join(escape(s) for s in (oauth["scopes"] or [])[:12]), st["body_sm"]))
    story.append(Spacer(1, 3 * mm))

    tok = br.get("token_misuse_analysis") or {}
    story.append(Paragraph("Token Misuse Analysis", st["h2"]))
    story.append(Paragraph(
        f"Tokens found: <b>{tok.get('tokens_detected', 0)}</b>. "
        f"Long-lived: {tok.get('long_lived_tokens', 0)}. "
        f"Rotation disabled: <b>{tok.get('token_rotation_disabled', False)}</b>. "
        f"Reuse across integrations: <b>{tok.get('token_reuse_across_integrations', False)}</b>. "
        f"Token risk score: <b>{tok.get('token_risk_score', 0):.1f}</b>.",
        st["body_sm"],
    ))
    story.append(Spacer(1, 3 * mm))

    cred = br.get("credential_exposure_analysis") or {}
    story.append(Paragraph("Credential Exposure Analysis", st["h2"]))
    story.append(Paragraph(f"Total exposed: <b>{cred.get('total_exposed_credentials', 0)}</b>. Risk score: <b>{cred.get('credential_risk_score', 0):.1f}</b>.", st["body_sm"]))
    findings_list = cred.get("findings", [])[:8]
    if findings_list:
        rows = [[Paragraph("Credential Type", st["tbl_header"]), Paragraph("Method", st["tbl_header"]), Paragraph("Severity", st["tbl_header"]), Paragraph("Location", st["tbl_header"])]]
        for cf in findings_list:
            if isinstance(cf, dict):
                rows.append([
                    Paragraph(escape(str(cf.get("credential_type", "—"))[:25]), st["tbl_cell"]),
                    Paragraph(escape(str(cf.get("detection_method", "—"))), st["tbl_cell_center"]),
                    Paragraph(escape(str(cf.get("severity", "—"))), st["tbl_cell_center"]),
                    Paragraph(escape(str(cf.get("location", "—"))[:35]), st["tbl_cell"]),
                ])
        tbl = Table(rows, colWidths=[45 * mm, 22 * mm, 25 * mm, 85 * mm], repeatRows=1)
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), _NAVY),
            ("TEXTCOLOR", (0, 0), (-1, 0), _WHITE),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [_LIGHT_GRAY, _WHITE]),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("BOX", (0, 0), (-1, -1), 0.5, _MID_GRAY),
            ("INNERGRID", (0, 0), (-1, -1), 0.3, _MID_GRAY),
        ]))
        story.append(tbl)
    story.append(Spacer(1, 3 * mm))

    flow = br.get("data_flow_risk_analysis") or {}
    story.append(Paragraph("Data Flow Risk Analysis", st["h2"]))
    story.append(Paragraph(
        f"Source: <b>{flow.get('source_saas', '—')}</b>. Destination: <b>{flow.get('destination_saas', '—')}</b>. "
        f"Sensitive data exposure: <b>{flow.get('sensitive_data_exposure', False)}</b>. "
        f"Cross-platform risk: <b>{flow.get('cross_platform_risk_detected', False)}</b>. "
        f"Data flow risk score: <b>{flow.get('data_flow_risk_score', 0):.1f}</b>.",
        st["body_sm"],
    ))
    return story


def _risk_graph_summary_section(report: ScanReport, st: dict) -> list:
    """Risk Graph Summary — nodes, edges, highest risk edge, findings on edge."""
    story: list = []
    summary = getattr(report, "risk_graph_summary", None)
    if not summary or not isinstance(summary, dict):
        return story
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph("Risk Graph Summary", st["h1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=_BLUE_LIGHT, spaceAfter=6))
    nodes = summary.get("nodes_discovered") or []
    edges = summary.get("edges") or []
    story.append(Paragraph(f"Nodes: <b>{', '.join(escape(str(n)) for n in nodes[:15]) or '—'}</b>", st["body"]))
    story.append(Paragraph(f"Connections discovered: <b>{summary.get('connections_discovered', 0)}</b>. Total graph risk score: <b>{summary.get('total_graph_risk_score', 0):.1f}</b>.", st["body_sm"]))
    high = summary.get("highest_risk_edge")
    if high and isinstance(high, dict):
        story.append(Paragraph(f"Highest risk edge: {escape(str(high.get('source', '—')))} → {escape(str(high.get('target', '—')))} (score: {high.get('risk_score', 0):.1f})", st["body_sm"]))
    findings_on_edge = summary.get("findings_on_edge") or []
    if findings_on_edge:
        story.append(Paragraph("Findings on edge: " + ", ".join(escape(str(f)[:30]) for f in findings_on_edge[:5]), st["body_sm"]))
    if edges:
        story.append(Spacer(1, 3 * mm))
        rows = [[Paragraph("Source", st["tbl_header"]), Paragraph("Target", st["tbl_header"]), Paragraph("Type", st["tbl_header"]), Paragraph("Risk", st["tbl_header"])]]
        for e in edges[:8]:
            if isinstance(e, dict):
                rows.append([
                    Paragraph(escape(str(e.get("source", "—"))), st["tbl_cell"]),
                    Paragraph(escape(str(e.get("target", "—"))), st["tbl_cell"]),
                    Paragraph(escape(str(e.get("connection_type", "—"))), st["tbl_cell_center"]),
                    Paragraph(str(e.get("risk_score", 0)), st["tbl_cell_center"]),
                ])
        tbl = Table(rows, colWidths=[40 * mm, 40 * mm, 35 * mm, 62 * mm], repeatRows=1)
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), _TEAL),
            ("TEXTCOLOR", (0, 0), (-1, 0), _WHITE),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [_LIGHT_GRAY, _WHITE]),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("BOX", (0, 0), (-1, -1), 0.5, _MID_GRAY),
            ("INNERGRID", (0, 0), (-1, -1), 0.3, _MID_GRAY),
        ]))
        story.append(tbl)
    return story


def _dataset_context_section(report: ScanReport, st: dict) -> list:
    """Dataset Context — when scan is from batch run."""
    story: list = []
    ctx = getattr(report, "dataset_context", None)
    if not ctx or not isinstance(ctx, dict):
        return story
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph("Dataset Context", st["h1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=_BLUE_LIGHT, spaceAfter=6))
    rows = [
        ["Dataset Name", ctx.get("dataset_name", "—")],
        ["Total Integrations Analyzed", str(ctx.get("total_integrations", "—"))],
        ["Average Risk Score", str(ctx.get("average_risk_score", "—"))],
        ["Credential Exposure Hits", str(ctx.get("credential_exposure_hits", "—"))],
        ["Token Misuse Hits", str(ctx.get("token_misuse_hits", "—"))],
        ["OAuth Over-permission Hits", str(ctx.get("oauth_over_permission_hits", "—"))],
        ["Cross-platform Risk Hits", str(ctx.get("cross_platform_risk_hits", "—"))],
    ]
    tbl_data = [[Paragraph(escape(r[0]), st["tbl_cell"]), Paragraph(escape(str(r[1])), st["tbl_cell"])] for r in rows]
    tbl = Table(tbl_data, colWidths=[55 * mm, 122 * mm])
    tbl.setStyle(TableStyle([
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [_LIGHT_GRAY, _WHITE]),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("BOX", (0, 0), (-1, -1), 0.5, _MID_GRAY),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, _MID_GRAY),
    ]))
    story.append(tbl)
    return story


def _pipeline_trace_section(report: ScanReport, st: dict) -> list:
    """Analysis Pipeline Trace — steps executed."""
    story: list = []
    steps = getattr(report, "pipeline_trace", None) or []
    if not steps:
        return story
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph("Analysis Pipeline Trace", st["h1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=_BLUE_LIGHT, spaceAfter=6))
    story.append(Paragraph("Pipeline steps executed during this scan:", st["body"]))
    story.append(Spacer(1, 2 * mm))
    for i, step in enumerate(steps, 1):
        story.append(Paragraph(f"{i}. {escape(step)}", st["body_sm"]))
    return story


def _attack_scenario_section(report: ScanReport, st: dict) -> list:
    """Potential Attack Scenario — steps and impact."""
    story: list = []
    scenario = getattr(report, "attack_scenario", None)
    if not scenario or not isinstance(scenario, dict):
        return story
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph("Potential Attack Scenario", st["h1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=_BLUE_LIGHT, spaceAfter=6))
    steps = scenario.get("steps", [])
    for i, step in enumerate(steps[:8], 1):
        story.append(Paragraph(f"{i}. {escape(step)}", st["body"]))
    story.append(Spacer(1, 3 * mm))
    impact = scenario.get("impact", "")
    if impact:
        story.append(Paragraph("<b>Impact:</b> " + escape(impact), st["body"]))
    return story


def _risk_breakdown(report: ScanReport, st: dict) -> list:
    story: list = []
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph("Risk Score Breakdown", st["h1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=_BLUE_LIGHT, spaceAfter=6))

    ctx_score  = report.metadata.get("context_score", 0.0)
    txt_score  = report.metadata.get("text_scan_score", 0.0)
    comb_score = report.risk_score

    story.append(Paragraph(
        "The composite risk score is computed from four SaaS risk dimensions using a "
        "weighted formula with CVSS-inspired severity ceilings. <b>OAuth Risk</b> measures "
        "scope over-permission. <b>Token Risk</b> covers API key/token misuse. "
        "<b>Credential Risk</b> is derived from text-scan detection. <b>Data Flow Risk</b> "
        "reflects cross-platform sensitive data movement.",
        st["body"],
    ))
    story.append(Spacer(1, 4 * mm))

    saas = report.metadata.get("saas_signals", {})
    oauth_score = saas.get("oauth", {}).get("scope_risk_score", 0.0)
    token_score = saas.get("tokens", {}).get("token_risk_score", 0.0)
    cred_score = saas.get("credentials", {}).get("credential_risk_score", 0.0)
    flow_score = saas.get("data_flow", {}).get("flow_risk_score", 0.0)

    _score_label_style = ParagraphStyle(
        "score_lbl",
        fontName="Helvetica-Bold",
        fontSize=9,
        textColor=_TEXT,
        leading=13,
    )
    for label, score in [
        ("OAuth Scope Risk", oauth_score),
        ("Token Misuse Risk", token_score),
        ("Credential Exposure Risk", cred_score),
        ("Data Flow Risk", flow_score),
        ("Context Score (pattern rules)", ctx_score),
        ("Text-Scan Score (regex / keyword / entropy)", txt_score),
        ("Combined Risk Score", comb_score),
    ]:
        bar_col = _risk_color(score)
        score_val_style = ParagraphStyle(
            "score_val",
            fontName="Helvetica-Bold",
            fontSize=13,
            textColor=bar_col,
            alignment=TA_CENTER,
            leading=16,
        )
        row = [
            Paragraph(label, _score_label_style),
            _RiskGauge(score, width=90 * mm, height=16),
            Paragraph(f"<b>{score:.1f}</b>", score_val_style),
        ]
        tbl = Table([row], colWidths=[72 * mm, 90 * mm, 25 * mm])
        tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), _WHITE),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING",   (0, 0), (0,  -1), 10),
            ("LEFTPADDING",   (1, 0), (1,  -1), 6),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
            ("TOPPADDING",    (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("BOX",           (0, 0), (-1, -1), 0.5, _MID_GRAY),
            ("LINEBEFORE",    (1, 0), (1,  -1), 0.3, _MID_GRAY),
            ("LINEBEFORE",    (2, 0), (2,  -1), 0.3, _MID_GRAY),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 2 * mm))

    return story


def _matched_rules_section(report: ScanReport, st: dict) -> list:
    story: list = []
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph("Matched Rules", st["h1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=_BLUE_LIGHT, spaceAfter=6))

    if not report.matched_rules:
        story.append(Paragraph("No rules matched during this scan.", st["body"]))
        return story

    header = [
        Paragraph("Rule Name", st["tbl_header"]),
        Paragraph("Severity", st["tbl_header"]),
        Paragraph("Weight", st["tbl_header"]),
    ]
    rows = [header]
    for i, rule in enumerate(report.matched_rules):
        sev_col = _SEV_COLORS.get(rule.severity, _MID_GRAY)
        sev_lbl = _SEV_LABELS.get(rule.severity, str(rule.severity))
        bg = _LIGHT_GRAY if i % 2 == 0 else _WHITE
        rows.append([
            Paragraph(rule.rule_name, st["tbl_cell"]),
            Paragraph(
                f'<font color="{sev_col.hexval()}"><b>{sev_lbl}</b></font>',
                st["tbl_cell_center"],
            ),
            Paragraph(str(rule.weight), st["tbl_cell_center"]),
        ])

    col_widths = [120 * mm, 35 * mm, 22 * mm]
    tbl = Table(rows, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), _WHITE),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [_LIGHT_GRAY, _WHITE]),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("BOX", (0, 0), (-1, -1), 0.5, _MID_GRAY),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, _MID_GRAY),
    ]))
    story.append(tbl)
    return story


def _findings_section(report: ScanReport, st: dict) -> list:
    story: list = []
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph("Findings", st["h1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=_BLUE_LIGHT, spaceAfter=6))

    if not report.findings:
        story.append(Paragraph("No text-scan findings detected in this scan.", st["body"]))
        return story

    story.append(Paragraph(
        f"The text-scan engine identified <b>{len(report.findings)}</b> finding(s). "
        "Each finding includes rule ID, detection method, severity, evidence, and integration context.",
        st["body"],
    ))
    story.append(Spacer(1, 3 * mm))

    integration_ctx = report.metadata.get("target", "—")
    header = [
        Paragraph("#", st["tbl_header"]),
        Paragraph("Rule ID", st["tbl_header"]),
        Paragraph("Detection Method", st["tbl_header"]),
        Paragraph("Severity", st["tbl_header"]),
        Paragraph("Evidence", st["tbl_header"]),
        Paragraph("Integration", st["tbl_header"]),
    ]
    rows = [header]
    for i, f in enumerate(report.findings, 1):
        sev_col = _SEV_COLORS.get(f.severity, _MID_GRAY)
        sev_lbl = _SEV_LABELS.get(f.severity, str(f.severity))
        evidence = f.evidence.replace("\n", " ").replace("\r", "")
        if len(evidence) > 80:
            evidence = evidence[:77] + "..."
        rows.append([
            Paragraph(str(i), st["tbl_cell_center"]),
            Paragraph(f.rule_id, st["tbl_cell"]),
            Paragraph((f.category or "—").upper(), st["tbl_cell_center"]),
            Paragraph(
                f'<font color="{sev_col.hexval()}"><b>{sev_lbl}</b></font>',
                st["tbl_cell_center"],
            ),
            Paragraph(f'<font face="Courier" size="7">{evidence}</font>', st["tbl_cell"]),
            Paragraph(escape(str(integration_ctx)[:20]), st["tbl_cell"]),
        ])

    col_widths = [8 * mm, 28 * mm, 22 * mm, 18 * mm, 65 * mm, 25 * mm]
    tbl = Table(rows, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), _WHITE),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [_LIGHT_GRAY, _WHITE]),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("BOX", (0, 0), (-1, -1), 0.5, _MID_GRAY),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, _MID_GRAY),
    ]))
    story.append(tbl)
    return story


def _recommendations_section(report: ScanReport, st: dict) -> list:
    """Generate dynamic recommendations from report.remediation_recommendations or legacy logic."""
    story: list = []
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph("Recommendations", st["h1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=_BLUE_LIGHT, spaceAfter=6))

    recs: list[tuple[int, str, str]] = []  # (priority, title, body)

    # Prefer structured remediation_recommendations when present (with component, risk, framework)
    struct_recs = getattr(report, "remediation_recommendations", None) or []
    if struct_recs and isinstance(struct_recs, list):
        for r in struct_recs:
            if isinstance(r, dict):
                pri = 1 if (r.get("priority") or "").lower() == "high" else 2
                title = r.get("title") or "Remediation"
                body = r.get("body") or ""
                if title or body:
                    recs.append((pri, escape(str(title)), escape(str(body)), r))
        if recs:
            recs.sort(key=lambda x: x[0])
            priority_labels = {1: ("CRITICAL ACTION", colors.HexColor("#7F1D1D")),
                              2: ("IMPORTANT", colors.HexColor("#EF4444")),
                              3: ("ADVISORY", colors.HexColor("#F59E0B"))}
            for idx, rec in enumerate(recs, 1):
                pri, title, body = rec[0], rec[1], rec[2]
                extra = rec[3] if len(rec) > 3 else {}
                p_label, p_color = priority_labels.get(pri, ("ADVISORY", _BLUE))
                badge_tbl = Table([[
                    Paragraph(f'<font color="white"><b>{p_label}</b></font>',
                              ParagraphStyle("pb", fontName="Helvetica-Bold", fontSize=7.5,
                                             textColor=_WHITE, alignment=TA_CENTER)),
                    Paragraph(f'<b>{idx}. {title}</b>', st["recommend_title"]),
                ]], colWidths=[28 * mm, 149 * mm])
                badge_tbl.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (0, 0), p_color),
                    ("BACKGROUND", (1, 0), (1, 0), _LIGHT_GRAY),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]))
                flowables = [badge_tbl, Paragraph(body, st["recommend_body"])]
                if extra.get("affected_component") or extra.get("risk_explanation") or extra.get("compliance_framework"):
                    lines = []
                    if extra.get("affected_component"):
                        lines.append(f"<b>Affected component:</b> {escape(str(extra['affected_component']))}")
                    if extra.get("risk_explanation"):
                        lines.append(f"<b>Risk:</b> {escape(str(extra['risk_explanation']))}")
                    if extra.get("compliance_framework"):
                        lines.append(f"<b>Compliance:</b> {escape(str(extra['compliance_framework']))}")
                    flowables.append(Paragraph("  ".join(lines), st["body_sm"]))
                flowables.append(Spacer(1, 2 * mm))
                story.append(KeepTogether(flowables))
            return story

    # Legacy: build from findings and signals

    finding_rule_ids = {f.rule_id for f in report.findings}

    # SaaS-specific recommendations from the analysis dimensions
    oauth = report.oauth_analysis
    tokens = report.token_analysis
    creds = report.credential_exposure
    flow = report.data_flow_risk

    if oauth and oauth.over_permissioned:
        wc = ", ".join(oauth.wildcard_scopes[:3]) if oauth.wildcard_scopes else "broad access scopes"
        recs.append((1, "Reduce OAuth Scope Over-Permission",
            f"The integration requests {oauth.total_scopes} scopes including over-privileged "
            f"grants ({wc}). Apply least-privilege principles — remove wildcard and admin "
            f"scopes, use read-only scopes where possible, and implement incremental consent "
            f"flows. Review the OAuth scopes policy for approved scope sets."))

    if tokens and tokens.rotation_disabled:
        recs.append((1, "Enable Token Rotation",
            "API token rotation is disabled for this integration. Long-lived, unrotated "
            "tokens are a primary credential-compromise vector. Enable automatic rotation, "
            "set short TTLs (< 90 days), and implement token revocation."))

    if tokens and tokens.tokens_in_urls > 0:
        recs.append((1, "Remove Tokens from URL Parameters",
            "Access tokens were detected in URL query strings. This exposes credentials in "
            "server logs, browser history, and referrer headers. Migrate to Authorization "
            "headers (Bearer tokens) or secure HTTP-only cookies."))

    if tokens and tokens.shared_across_integrations:
        recs.append((1, "Eliminate Token Reuse Across Integrations",
            "The same token value is shared across multiple SaaS integrations. A single "
            "compromise would cascade across all connected services. Issue unique tokens "
            "per integration and implement per-service scoping."))

    if flow and flow.cross_platform_risk:
        src = flow.source_app or "source"
        dst = flow.destination_app or "destination"
        dtypes = ", ".join(flow.data_types[:3]) if flow.data_types else "sensitive data"
        recs.append((1, "Review Cross-Platform Data Exposure",
            f"Sensitive data ({dtypes}) flows from {src} to {dst}. Ensure data classification "
            f"policies are enforced, implement DLP controls at integration boundaries, and "
            f"verify that the receiving platform meets your security and compliance requirements."))

    if "saas_bearer_token" in finding_rule_ids:
        recs.append((1, "Rotate Exposed Bearer Tokens",
            "Bearer token patterns were found in the integration configuration. Rotate "
            "immediately, implement secrets management (Vault, AWS Secrets Manager), and "
            "ensure tokens never appear in plaintext artifacts."))

    if "saas_oauth_client_secret" in finding_rule_ids:
        recs.append((1, "Secure OAuth Client Secrets",
            "OAuth client secrets were found in plaintext. Move them to a secure vault, "
            "use certificate-based authentication where supported, and audit access to "
            "secret storage."))

    if "saas_private_key_block" in finding_rule_ids:
        recs.append((1, "Remove Embedded Private Keys",
            "A private key PEM block was found in the integration artifact. Private key "
            "material must never appear in configs or logs. Rotate the key, store it in "
            "a HSM or vault, and audit who had access to the artifact."))

    if any(rid in finding_rule_ids for rid in ("saas_aws_access_key", "saas_github_pat", "saas_slack_token")):
        recs.append((1, "Rotate Platform-Specific Credentials",
            "A vendor-specific credential (AWS key, GitHub PAT, or Slack token) was detected "
            "in plaintext. Rotate immediately via the provider's console and migrate to "
            "short-lived, scoped credentials."))

    if creds and creds.exposed_credentials > 0 and not any(r[1].startswith("Rotate") for r in recs):
        recs.append((2, "Audit Exposed Credentials",
            f"{creds.exposed_credentials} credential exposure(s) detected. Review the "
            f"findings table, rotate all affected credentials, and enforce static analysis "
            f"in CI/CD to prevent committed secrets."))

    if tokens and tokens.long_lived_tokens > 0:
        recs.append((2, "Shorten Token Lifetimes",
            "Long-lived tokens (>= 90 days) increase the window for credential abuse. "
            "Reduce TTLs to under 30 days where possible, implement refresh-token rotation, "
            "and monitor for anomalous token usage."))

    if not recs and report.findings:
        recs.append((2, "Investigate Detected Findings",
            "One or more risk patterns triggered during analysis. Review the findings table "
            "and assess whether sensitive data exposure or policy violations exist."))

    if not recs and not report.findings:
        story.append(Paragraph(
            "No critical risk patterns were detected. Continue to monitor SaaS integrations "
            "regularly and keep the YAML policy rules up to date with emerging threat patterns.",
            st["body"],
        ))
        return story

    # Sort by priority then render
    recs.sort(key=lambda x: x[0])
    priority_labels = {1: ("CRITICAL ACTION", colors.HexColor("#7F1D1D")),
                       2: ("IMPORTANT", colors.HexColor("#EF4444")),
                       3: ("ADVISORY", colors.HexColor("#F59E0B"))}

    for idx, (pri, title, body) in enumerate(recs, 1):
        p_label, p_color = priority_labels.get(pri, ("ADVISORY", _BLUE))
        badge_tbl = Table([[
            Paragraph(f'<font color="white"><b>{p_label}</b></font>',
                      ParagraphStyle("pb", fontName="Helvetica-Bold", fontSize=7.5,
                                     textColor=_WHITE, alignment=TA_CENTER)),
            Paragraph(f'<b>{idx}. {title}</b>', st["recommend_title"]),
        ]], colWidths=[28 * mm, 149 * mm])
        badge_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, 0), p_color),
            ("BACKGROUND", (1, 0), (1, 0), _LIGHT_GRAY),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        body_para = Paragraph(body, st["recommend_body"])
        story.append(KeepTogether([badge_tbl, body_para, Spacer(1, 2 * mm)]))

    return story


def _rules_appendix(report: ScanReport, st: dict) -> list:
    """Appendix: full rules inventory loaded directly from rules file."""
    from app.core.config import settings
    from app.services.rules_loader import load_rules

    story: list = []
    try:
        rule_set = load_rules()
    except Exception:
        return story

    path = settings.rules_path

    story.append(PageBreak())
    story.append(Paragraph("Appendix — Active Rules Inventory", st["h1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=_BLUE_LIGHT, spaceAfter=6))
    story.append(Paragraph(
        f"Rules file: <b>{path.name}</b>  ·  "
        f"Context rules: <b>{len(rule_set.rules)}</b>  ·  "
        f"Text-scan rules: <b>{len(rule_set.text_scan_rules)}</b>  ·  "
        f"Total: <b>{len(rule_set.rules) + len(rule_set.text_scan_rules)}</b>",
        st["body"],
    ))
    story.append(Spacer(1, 3 * mm))

    if rule_set.rules:
        story.append(Paragraph("Context (Pattern) Rules", st["h2"]))
        h = [Paragraph(x, st["tbl_header"]) for x in
             ["Rule Name", "Severity", "Weight", "Patterns", "Enabled"]]
        rows = [h]
        for i, r in enumerate(rule_set.rules):
            sev_col = _SEV_COLORS.get(r.severity, _MID_GRAY)
            rows.append([
                Paragraph(r.name, st["tbl_cell"]),
                Paragraph(f'<font color="{sev_col.hexval()}"><b>{r.severity}</b></font>',
                          st["tbl_cell_center"]),
                Paragraph(str(r.weight), st["tbl_cell_center"]),
                Paragraph(str(len(r.patterns)), st["tbl_cell_center"]),
                Paragraph("✓" if r.enabled else "✗", st["tbl_cell_center"]),
            ])
        tbl = Table(rows, colWidths=[90 * mm, 22 * mm, 22 * mm, 22 * mm, 21 * mm],
                    repeatRows=1)
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), _BLUE),
            ("TEXTCOLOR", (0, 0), (-1, 0), _WHITE),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [_LIGHT_GRAY, _WHITE]),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("BOX", (0, 0), (-1, -1), 0.5, _MID_GRAY),
            ("INNERGRID", (0, 0), (-1, -1), 0.3, _MID_GRAY),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 4 * mm))

    if rule_set.text_scan_rules:
        story.append(Paragraph("Text-Scan Rules", st["h2"]))
        h = [Paragraph(x, st["tbl_header"]) for x in
             ["Rule ID", "Category", "Severity", "Weight", "Enabled", "Description"]]
        rows = [h]
        for i, r in enumerate(rule_set.text_scan_rules):
            sev_col = _SEV_COLORS.get(r.severity, _MID_GRAY)
            rows.append([
                Paragraph(r.id, st["tbl_cell"]),
                Paragraph(r.category.upper(), st["tbl_cell_center"]),
                Paragraph(f'<font color="{sev_col.hexval()}"><b>{r.severity}</b></font>',
                          st["tbl_cell_center"]),
                Paragraph(str(r.weight), st["tbl_cell_center"]),
                Paragraph("✓" if r.enabled else "✗", st["tbl_cell_center"]),
                Paragraph(r.description or "—", st["body_sm"]),
            ])
        tbl = Table(rows,
                    colWidths=[38 * mm, 22 * mm, 16 * mm, 16 * mm, 14 * mm, 71 * mm],
                    repeatRows=1)
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), _TEAL),
            ("TEXTCOLOR", (0, 0), (-1, 0), _WHITE),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [_LIGHT_GRAY, _WHITE]),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("ALIGN", (0, 0), (0, -1), "LEFT"),
            ("ALIGN", (5, 0), (5, -1), "LEFT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("BOX", (0, 0), (-1, -1), 0.5, _MID_GRAY),
            ("INNERGRID", (0, 0), (-1, -1), 0.3, _MID_GRAY),
        ]))
        story.append(tbl)

    return story


# ── Public entry point ────────────────────────────────────────────────────────

def generate_executive_pdf(report: ScanReport) -> bytes:
    """Generate a professional executive-grade PDF from *report*.

    Returns the PDF as raw bytes ready for streaming.
    """
    try:
        buf = io.BytesIO()
        w, h = A4
        st = _make_styles()

        ts_str = (report.timestamp.strftime("%Y-%m-%d %H:%M UTC")
                  if report.timestamp else datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))
        scan_id_short = str(report.scan_id)[:18] + "…"
        company_name, logo_bytes = _extract_branding(report)
        report_title = "SaaS Integration Risk Report"
        if company_name:
            report_title = f"{company_name} SaaS Integration Risk Report"
        logo_flowable = None
        if logo_bytes:
            try:
                logo_flowable = _build_logo_flowable(logo_bytes, max_w=45 * mm, max_h=16 * mm)
            except Exception:
                logger.warning("Failed to decode logo image; proceeding without logo", exc_info=True)
                logo_flowable = None
        if logo_flowable is None:
            logo_flowable = _DefaultLogo()

        # ── Document with two page templates ─────────────────────────────────
        cover_frame = Frame(0, 0, w, h, leftPadding=18 * mm, rightPadding=18 * mm,
                            topPadding=0, bottomPadding=15 * mm, id="cover")
        body_frame  = Frame(0, 0, w, h, leftPadding=18 * mm, rightPadding=18 * mm,
                            topPadding=32 * mm, bottomPadding=18 * mm, id="body")

        doc = BaseDocTemplate(
            buf,
            pagesize=A4,
            pageTemplates=[
                PageTemplate(id="cover", frames=[cover_frame],
                             onPage=_make_cover_cb(scan_id_short, ts_str)),
                PageTemplate(id="body",  frames=[body_frame],
                             onPage=_make_page_cb(scan_id_short, ts_str, report_title)),
            ],
        )

        # ── Story assembly ────────────────────────────────────────────────────
        story: list = []
        story += _cover_section(report, st, company_name, logo_flowable)
        story += _executive_summary(report, st)
        story += _analyzed_input_overview_section(report, st)
        story += _integration_metadata_section(report, st)
        story += _detection_signals_section(report, st)
        story += _integration_visibility_section(report, st)
        story += _analyzer_breakdown_section(report, st)
        story += _risk_graph_summary_section(report, st)
        story += _top_risky_connections_section(report, st)
        story += _ai_data_flow_risks_section(report, st)
        story += _risk_breakdown(report, st)
        story += _matched_rules_section(report, st)
        story += _findings_section(report, st)
        story += _compliance_mapping_section(report, st)
        story += _recommendations_section(report, st)
        story += _attack_scenario_section(report, st)
        story += _dataset_context_section(report, st)
        story += _rules_appendix(report, st)

        doc.build(story)
        pdf_bytes = buf.getvalue()
        logger.debug("Executive PDF generated: %d bytes, scan_id=%s",
                     len(pdf_bytes), report.scan_id)
        return pdf_bytes

    except Exception as e:
        logger.error("Executive PDF generation failed", exc_info=True)
        raise ServiceError(
            message="Executive PDF generation failed",
            detail={"error": str(e)},
        ) from e
