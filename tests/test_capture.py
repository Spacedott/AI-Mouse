"""Regressions for capture threading and the shared test-database setting."""
from __future__ import annotations

import importlib.util
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent"))
from mouse_ai_agent.config import Config  # noqa: E402
from mouse_ai_agent.virtual_desktop import VirtualDesktop  # noqa: E402


class TestConfig(unittest.TestCase):
    def test_environment_overrides_config_database(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "config.json"
            config.write_text('{"db_path":"data/config.db"}', encoding="utf-8")
            with mock.patch.dict(os.environ, {"MOUSE_AI_DB": "data/test.db"}):
                loaded = Config.load(config)
        self.assertEqual(Path(loaded.db_path), ROOT / "data" / "test.db")


@unittest.skipUnless(importlib.util.find_spec("pynput"), "Install agent requirements")
class TestCapture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with mock.patch.dict(os.environ, {"PYNPUT_BACKEND": "dummy"}):
            from mouse_ai_agent import capture
        cls.module = capture

    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.db = str(Path(directory) / "capture.db")
        self.enterContext(mock.patch.object(
            self.module, "get_virtual_desktop", return_value=VirtualDesktop(-1000, 0, 2000, 1000)))
        self.capture = self.module.ClickCapture(Config(self.db, 4, 4))
        self.addCleanup(self.capture.stop)

    def rows(self, sql):
        with closing(sqlite3.connect(self.db)) as conn:
            return conn.execute(sql).fetchall()

    def test_background_hook_clicks_are_written_in_order_on_the_owner_thread(self):
        module = self.module

        class FakeListener(threading.Thread):
            def __init__(self, on_click):
                super().__init__(daemon=True)
                self.on_click = on_click

            def run(self):
                for x, y in [(-900, 100), (300, 200), (-800, 300)]:
                    self.on_click(x, y, module.mouse.Button.left, True)
                    self.on_click(x, y, module.mouse.Button.left, False)

            def stop(self):
                pass

        with mock.patch.object(module.mouse, "Listener", side_effect=FakeListener):
            self.capture.run()
        self.assertEqual(self.rows("SELECT seq, x_virt, y_virt FROM clicks ORDER BY seq"),
                         [(1, -900, 100), (2, 300, 200), (3, -800, 300)])
        self.assertIsNotNone(self.rows("SELECT ended_t FROM sessions")[0][0])
        self.assertEqual(self.rows("SELECT SUM(total_clicks) FROM zone_totals")[0][0], 3)

    def test_shutdown_flushes_pending_clicks_and_ignores_releases(self):
        def hook():
            self.capture._on_click(-900, 100, self.module.mouse.Button.left, True)
            self.capture._on_click(-900, 100, self.module.mouse.Button.left, False)

        worker = threading.Thread(target=hook)
        worker.start()
        worker.join(timeout=2)
        self.assertFalse(worker.is_alive())
        self.capture.stop()
        self.assertEqual(self.rows("SELECT COUNT(*) FROM clicks")[0][0], 1)

    def test_shutdown_is_idempotent(self):
        self.capture.stop()
        self.capture.stop()
        self.assertEqual(len(self.rows("SELECT ended_t FROM sessions")), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
