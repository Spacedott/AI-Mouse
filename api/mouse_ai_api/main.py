"""Local API bridge: serves aggregates + PDF report to the dashboard.

A browser can't read the SQLite file directly, so this thin FastAPI app
reads the local store (read-only) and exposes JSON + a PDF endpoint.
Runs locally only; it does not upload anything anywhere.

Run:  uvicorn mouse_ai_api.main:app --port 8000
"""
from __future__ import annotations

import os
from contextlib import closing

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from . import queries, report

# Same default the agent uses; override with MOUSE_AI_DB.
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DB_PATH = os.environ.get("MOUSE_AI_DB", os.path.join(REPO_ROOT, "data", "mouse_ai.db"))

app = FastAPI(title="Mouse-AI API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # local dev; tighten for packaged builds
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/api/zones")
def get_zones():
    with closing(queries.open_ro(DB_PATH)) as conn:
        return queries.zone_totals(conn)


@app.get("/api/sessions")
def get_sessions():
    with closing(queries.open_ro(DB_PATH)) as conn:
        return queries.sessions(conn)


@app.get("/api/trends")
def get_trends():
    with closing(queries.open_ro(DB_PATH)) as conn:
        return queries.clicks_per_session(conn)


@app.get("/api/report.pdf")
def get_report(session_id: str | None = None):
    with closing(queries.open_ro(DB_PATH)) as conn:
        pdf = report.build_report_pdf(conn, session_id)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="mouse-ai-report.pdf"'},
    )
