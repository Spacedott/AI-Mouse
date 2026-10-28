"""Standard-library tests for the Mouse-AI data core.

Covers the pieces that don't need third-party deps or Windows:
  - grid zone mapping (agent.grid)
  - multi-monitor normalization (agent.virtual_desktop)
  - SQLite store: sessions, raw retention, zone aggregates (agent.store)
  - read queries used by the API (api.queries)

Run:  python3 -m unittest discover -s tests -v
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "agent"))
sys.path.insert(0, os.path.join(REPO_ROOT, "api"))

from mouse_ai_agent.grid import Grid                       # noqa: E402
from mouse_ai_agent.virtual_desktop import VirtualDesktop  # noqa: E402
from mouse_ai_agent import store                           # noqa: E402
from mouse_ai_api import queries                           # noqa: E402


class TestGrid(unittest.TestCase):
    def setUp(self):
        self.g = Grid(rows=4, cols=4)

    def test_corners(self):
        self.assertEqual(self.g.zone_id(0.0, 0.0), "r0c0")
        self.assertEqual(self.g.zone_id(0.999, 0.999), "r3c3")

    def test_cell_boundaries(self):
        # 4 cols -> each 0.25 wide. 0.25 starts col 1; 0.5 starts col 2.
        self.assertEqual(self.g.zone_id(0.24, 0.0), "r0c0")
        self.assertEqual(self.g.zone_id(0.25, 0.0), "r0c1")
        self.assertEqual(self.g.zone_id(0.50, 0.0), "r0c2")
        self.assertEqual(self.g.zone_id(0.75, 0.0), "r0c3")

    def test_row_mapping(self):
        self.assertEqual(self.g.zone_id(0.0, 0.5), "r2c0")

    def test_clamps_out_of_range(self):
        # Values at/over 1.0 must not spill past the last cell.
        self.assertEqual(self.g.zone_id(1.0, 1.0), "r3c3")
        self.assertEqual(self.g.zone_id(2.0, 2.0), "r3c3")
        self.assertEqual(self.g.zone_id(-1.0, -1.0), "r0c0")

    def test_all_zone_ids(self):
        ids = self.g.all_zone_ids()
        self.assertEqual(len(ids), 16)
        self.assertEqual(len(set(ids)), 16)  # all unique


class TestVirtualDesktop(unittest.TestCase):
    def test_single_monitor(self):
        vd = VirtualDesktop(x=0, y=0, w=1920, h=1080)
        self.assertEqual(vd.normalize(0, 0), (0.0, 0.0))
        nx, ny = vd.normalize(1919, 1079)
        self.assertAlmostEqual(nx, 1919 / 1920, places=4)
        self.assertAlmostEqual(ny, 1079 / 1080, places=4)

    def test_negative_origin_second_monitor_left(self):
        # 2nd monitor to the LEFT of primary -> virtual origin is negative.
        vd = VirtualDesktop(x=-1920, y=0, w=3840, h=1080)
        self.assertEqual(vd.normalize(-1920, 0), (0.0, 0.0))   # far-left edge
        nx, _ = vd.normalize(0, 0)                              # primary's origin
        self.assertAlmostEqual(nx, 0.5, places=4)              # halfway across

    def test_clamp_keeps_in_unit_range(self):
        vd = VirtualDesktop(x=0, y=0, w=1000, h=1000)
        nx, ny = vd.normalize(5000, -5000)
        self.assertTrue(0.0 <= nx < 1.0)
        self.assertTrue(0.0 <= ny < 1.0)


class TestStoreAndQueries(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = os.path.join(self.tmp, "test.db")
        self.grid = Grid(4, 4)
        self.vd = VirtualDesktop(x=-1920, y=0, w=3840, h=1080)
        self.conn = store.connect(self.db)
        store.init_db(self.conn)

    def tearDown(self):
        self.conn.close()

    def _click(self, sid, seq, x, y, button="left"):
        nx, ny = self.vd.normalize(x, y)
        store.record_click(
            self.conn, session_id=sid, seq=seq, t=time.time(),
            x_virt=x, y_virt=y, x_norm=nx, y_norm=ny,
            button=button, monitor_id=None, zone_id=self.grid.zone_id(nx, ny),
        )

    def test_session_lifecycle(self):
        sid = store.start_session(self.conn, 4, 4, self.vd.x, self.vd.y, self.vd.w, self.vd.h)
        row = self.conn.execute(
            "SELECT ended_t FROM sessions WHERE session_id=?", (sid,)).fetchone()
        self.assertIsNone(row["ended_t"])
        store.end_session(self.conn, sid)
        row = self.conn.execute(
            "SELECT ended_t FROM sessions WHERE session_id=?", (sid,)).fetchone()
        self.assertIsNotNone(row["ended_t"])

    def test_raw_retention_and_aggregates(self):
        sid = store.start_session(self.conn, 4, 4, self.vd.x, self.vd.y, self.vd.w, self.vd.h)
        # 3 clicks at primary origin (same zone), 1 at far corner (another zone).
        self._click(sid, 1, 0, 0)
        self._click(sid, 2, 0, 0)
        self._click(sid, 3, 0, 0)
        self._click(sid, 4, 3839, 1079)

        # Every raw click retained.
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM clicks").fetchone()[0], 4)

        # Aggregates reflect the counts.
        totals = {r["zone_id"]: r["total_clicks"] for r in queries.zone_totals(self.conn)}
        self.assertEqual(totals[self.grid.zone_id(*self.vd.normalize(0, 0))], 3)
        self.assertEqual(totals[self.grid.zone_id(*self.vd.normalize(3839, 1079))], 1)

    def test_queries_sessions_and_trends(self):
        s1 = store.start_session(self.conn, 4, 4, self.vd.x, self.vd.y, self.vd.w, self.vd.h)
        self._click(s1, 1, 0, 0)
        store.end_session(self.conn, s1)
        s2 = store.start_session(self.conn, 4, 4, self.vd.x, self.vd.y, self.vd.w, self.vd.h)
        self._click(s2, 1, 0, 0)
        self._click(s2, 2, 100, 100)

        sessions = queries.sessions(self.conn)
        self.assertEqual(len(sessions), 2)
        counts = {s["session_id"]: s["total_clicks"] for s in sessions}
        self.assertEqual(counts[s1], 1)
        self.assertEqual(counts[s2], 2)

        # Trends come back oldest-first.
        trend = queries.clicks_per_session(self.conn)
        self.assertEqual([t["session_id"] for t in trend], [s1, s2])

    def test_zone_totals_for_session(self):
        s1 = store.start_session(self.conn, 4, 4, self.vd.x, self.vd.y, self.vd.w, self.vd.h)
        self._click(s1, 1, 0, 0)
        self._click(s1, 2, 0, 0)
        per = queries.zone_totals_for_session(self.conn, s1)
        self.assertEqual(per[0]["total_clicks"], 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
