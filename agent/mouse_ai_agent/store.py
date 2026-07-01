"""SQLite persistence: raw click log (retained) + derived zone totals.

Shared by the agent (writer) and the API (reader). WAL mode lets the API
read while the agent writes.
"""
from __future__ import annotations

import sqlite3
import time
import uuid
from pathlib import Path

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "shared" / "schema.sql"


def connect(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()


def start_session(conn: sqlite3.Connection, grid_rows: int, grid_cols: int,
                  vx: int, vy: int, vw: int, vh: int) -> str:
    session_id = uuid.uuid4().hex
    conn.execute(
        "INSERT INTO sessions "
        "(session_id, started_t, grid_rows, grid_cols, vx, vy, vw, vh) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (session_id, time.time(), grid_rows, grid_cols, vx, vy, vw, vh),
    )
    conn.commit()
    return session_id


def end_session(conn: sqlite3.Connection, session_id: str) -> None:
    conn.execute(
        "UPDATE sessions SET ended_t = ? WHERE session_id = ?",
        (time.time(), session_id),
    )
    conn.commit()


def record_click(conn: sqlite3.Connection, *, session_id: str, seq: int, t: float,
                 x_virt: int, y_virt: int, x_norm: float, y_norm: float,
                 button: str, monitor_id: int | None, zone_id: str) -> None:
    """Insert one raw click and bump its zone total, atomically."""
    conn.execute(
        "INSERT INTO clicks "
        "(session_id, seq, t, x_virt, y_virt, x_norm, y_norm, button, monitor_id, zone_id) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (session_id, seq, t, x_virt, y_virt, x_norm, y_norm, button, monitor_id, zone_id),
    )
    conn.execute(
        "INSERT INTO zone_totals (zone_id, total_clicks, last_click_t) "
        "VALUES (?, 1, ?) "
        "ON CONFLICT(zone_id) DO UPDATE SET "
        "total_clicks = total_clicks + 1, last_click_t = excluded.last_click_t",
        (zone_id, t),
    )
    conn.commit()
