"""Generate a shareable PDF report from stored click data.

By default the report contains only AGGREGATED zone/trend data (no raw
coordinates), so it's safe to share. Uses reportlab (pure-Python, no
system deps).
"""
from __future__ import annotations

import io
import sqlite3
import time

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.platypus import (SimpleDocTemplate, Spacer, Table, TableStyle,
                                Paragraph)
from reportlab.lib.styles import getSampleStyleSheet

from . import queries


def build_report_pdf(conn: sqlite3.Connection, session_id: str | None = None) -> bytes:
    """Return PDF bytes for all-time (session_id=None) or one session."""
    styles = getSampleStyleSheet()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter,
                            title="Mouse-AI Usage Report")
    story = []

    scope = "All sessions" if session_id is None else f"Session {session_id[:8]}"
    story.append(Paragraph("Mouse-AI — Usage Report", styles["Title"]))
    story.append(Paragraph(f"Scope: {scope}", styles["Normal"]))
    story.append(Paragraph(
        f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}", styles["Normal"]))
    story.append(Spacer(1, 0.3 * inch))

    if session_id is None:
        zones = queries.zone_totals(conn)
    else:
        zones = queries.zone_totals_for_session(conn, session_id)

    total = sum(z["total_clicks"] for z in zones) or 1
    story.append(Paragraph(f"Total clicks: {total}", styles["Heading2"]))
    story.append(Spacer(1, 0.15 * inch))

    data = [["Zone", "Clicks", "Share"]]
    for z in zones:
        share = 100.0 * z["total_clicks"] / total
        data.append([z["zone_id"], str(z["total_clicks"]), f"{share:.1f}%"])

    table = Table(data, hAlign="LEFT", colWidths=[1.5 * inch, 1.2 * inch, 1.2 * inch])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#333333")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f2f2")]),
    ]))
    story.append(table)

    doc.build(story)
    return buf.getvalue()
