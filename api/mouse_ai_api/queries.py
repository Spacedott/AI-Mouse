"""Read-only aggregate queries over the local store (used by the API)."""
from __future__ import annotations

import sqlite3


def open_ro(db_path: str) -> sqlite3.Connection:
    """Open the store read-only so the API never blocks the agent's writes."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def zone_totals(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT zone_id, total_clicks, last_click_t "
        "FROM zone_totals ORDER BY total_clicks DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def sessions(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT session_id, started_t, ended_t, grid_rows, grid_cols, "
        "(SELECT COUNT(*) FROM clicks c WHERE c.session_id = s.session_id) AS total_clicks "
        "FROM sessions s ORDER BY started_t DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def clicks_per_session(conn: sqlite3.Connection) -> list[dict]:
    """Trend data: total clicks per session, oldest first."""
    rows = conn.execute(
        "SELECT session_id, started_t, "
        "(SELECT COUNT(*) FROM clicks c WHERE c.session_id = s.session_id) AS clicks "
        "FROM sessions s ORDER BY started_t ASC"
    ).fetchall()
    return [dict(r) for r in rows]


def zone_totals_for_session(conn: sqlite3.Connection, session_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT zone_id, COUNT(*) AS total_clicks "
        "FROM clicks WHERE session_id = ? GROUP BY zone_id "
        "ORDER BY total_clicks DESC",
        (session_id,),
    ).fetchall()
    return [dict(r) for r in rows]
