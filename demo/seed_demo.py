"""Create the demo click store, optionally pre-filled with sample history.

The demo uses its own database (data/demo.db by default), so presenting never
mixes sample clicks into your real store at data/mouse_ai.db.

    python demo/seed_demo.py              # sample history (keeps an existing demo DB)
    python demo/seed_demo.py --reset      # wipe the demo DB, then add sample history
    python demo/seed_demo.py --reset --empty   # wipe and start with no clicks

The sample history is a week of made-up "Word + browser" sessions so the
dashboard has trends to show before the live session starts.
"""
from __future__ import annotations

import argparse
import os
import random
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "agent"))

from mouse_ai_agent import store                                 # noqa: E402
from mouse_ai_agent.config import Config                         # noqa: E402
from mouse_ai_agent.grid import Grid                             # noqa: E402
from mouse_ai_agent.virtual_desktop import get_virtual_desktop   # noqa: E402

DEFAULT_DB = REPO_ROOT / "data" / "demo.db"

# Normalized (x, y) hotspots on the virtual desktop, with spread and weight.
# Loosely modeled on a maximized Word window and a browser on one screen.
HOTSPOTS = [
    ((0.10, 0.08), 0.04, 30),   # Word ribbon: Home tab (bold, styles, fonts)
    ((0.03, 0.02), 0.01, 8),    # Quick Access: Save / Undo
    ((0.30, 0.03), 0.06, 10),   # browser tabs / address bar
    ((0.50, 0.50), 0.20, 25),   # document body: placing the cursor
    ((0.98, 0.45), 0.02, 9),    # scroll bar
    ((0.50, 0.98), 0.15, 8),    # taskbar
    ((0.85, 0.08), 0.03, 6),    # ribbon: Review / Share
]


def _sample_point(rng: random.Random) -> tuple[float, float]:
    (cx, cy), spread, _ = rng.choices(HOTSPOTS, weights=[h[2] for h in HOTSPOTS])[0]
    x = min(0.999, max(0.0, rng.gauss(cx, spread)))
    y = min(0.999, max(0.0, rng.gauss(cy, spread)))
    return x, y


def seed(db_path: str, grid: Grid, sessions: int, rng: random.Random) -> int:
    vd = get_virtual_desktop()
    conn = store.connect(db_path)
    store.init_db(conn)
    now = time.time()
    total = 0
    with conn:
        for i in range(sessions):
            # One session per day, oldest first, each 20-50 minutes long.
            started = now - (sessions - i) * 86400 + rng.uniform(-3600, 3600)
            length = rng.uniform(1200, 3000)
            session_id = f"demo{i:04d}" + os.urandom(12).hex()
            conn.execute(
                "INSERT INTO sessions (session_id, started_t, ended_t, grid_rows, "
                "grid_cols, vx, vy, vw, vh) VALUES (?,?,?,?,?,?,?,?,?)",
                (session_id, started, started + length, grid.rows, grid.cols,
                 vd.x, vd.y, vd.w, vd.h),
            )
            # Usage grows over the week, which makes the trend chart readable.
            clicks = int(rng.uniform(60, 110) * (1 + i * 0.25))
            times = sorted(rng.uniform(started, started + length) for _ in range(clicks))
            for seq, t in enumerate(times, start=1):
                x_norm, y_norm = _sample_point(rng)
                conn.execute(
                    "INSERT INTO clicks (session_id, seq, t, x_virt, y_virt, x_norm, "
                    "y_norm, button, monitor_id, zone_id) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (session_id, seq, t, vd.x + int(x_norm * vd.w),
                     vd.y + int(y_norm * vd.h), x_norm, y_norm,
                     "right" if rng.random() < 0.08 else "left", None,
                     grid.zone_id(x_norm, y_norm)),
                )
            total += clicks
        # zone_totals is a cache over clicks; rebuild it from the raw log.
        conn.execute("DELETE FROM zone_totals")
        conn.execute(
            "INSERT INTO zone_totals (zone_id, total_clicks, last_click_t) "
            "SELECT zone_id, COUNT(*), MAX(t) FROM clicks GROUP BY zone_id"
        )
    conn.close()
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default=os.environ.get("MOUSE_AI_DB", str(DEFAULT_DB)))
    parser.add_argument("--reset", action="store_true", help="delete the demo DB first")
    parser.add_argument("--empty", action="store_true", help="create the schema only")
    parser.add_argument("--sessions", type=int, default=6)
    parser.add_argument("--seed", type=int, default=7, help="random seed")
    args = parser.parse_args()

    db = Path(args.db).resolve()
    if db.resolve() == (REPO_ROOT / "data" / "mouse_ai.db").resolve():
        sys.exit("Refusing to seed the real click store; use a separate demo DB.")
    if args.reset:
        for suffix in ("", "-wal", "-shm"):
            Path(f"{db}{suffix}").unlink(missing_ok=True)

    cfg = Config.load()
    grid = Grid(rows=cfg.grid_rows, cols=cfg.grid_cols)
    conn = store.connect(str(db))
    store.init_db(conn)
    has_data = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] > 0
    # Stop-Demo force-closes the agent, so its session never gets an end time.
    # Close those at their last click so only the next run shows as live.
    with conn:
        conn.execute(
            "UPDATE sessions SET ended_t = COALESCE("
            "(SELECT MAX(t) FROM clicks c WHERE c.session_id = sessions.session_id), "
            "started_t) WHERE ended_t IS NULL"
        )
    conn.close()

    if args.empty or has_data:
        print(f"[demo] store ready at {db} ({'kept existing data' if has_data else 'empty'})")
        return
    total = seed(str(db), grid, args.sessions, random.Random(args.seed))
    print(f"[demo] seeded {args.sessions} sample sessions / {total} clicks into {db}")


if __name__ == "__main__":
    main()
