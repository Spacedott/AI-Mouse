"""Exercise the actual local HTTP API and PDF export with a temporary store."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import socket
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "agent"), str(ROOT / "api")]
HAS_API = all(importlib.util.find_spec(name) is not None
              for name in ("fastapi", "uvicorn", "reportlab"))


@unittest.skipUnless(HAS_API, "Install API requirements")
class TestAPI(unittest.TestCase):
    def test_clicks_reach_http_totals_sessions_trends_and_pdf(self):
        import uvicorn
        from mouse_ai_agent import store
        from mouse_ai_api import main as api

        # Windows also verifies all request connections close: otherwise the
        # temporary SQLite file remains locked when this directory is removed.
        with tempfile.TemporaryDirectory() as directory:
            db = str(Path(directory) / "test.db")
            conn = store.connect(db)
            try:
                store.init_db(conn)
                sid = store.start_session(conn, 4, 4, -1000, 0, 2000, 1000)
                for seq in range(1, 4):
                    store.record_click(conn, session_id=sid, seq=seq, t=time.time(),
                                       x_virt=-900, y_virt=100, x_norm=.05, y_norm=.1,
                                       button="left", monitor_id=None, zone_id="r0c0")
                store.end_session(conn, sid)
            finally:
                conn.close()

            with mock.patch.object(api, "DB_PATH", db):
                listener = socket.socket()
                listener.bind(("127.0.0.1", 0))
                port = listener.getsockname()[1]
                server = uvicorn.Server(uvicorn.Config(api.app, log_level="error"))
                worker = threading.Thread(target=server.run,
                                          kwargs={"sockets": [listener]}, daemon=True)
                worker.start()
                try:
                    deadline = time.monotonic() + 10
                    while not server.started and worker.is_alive() and time.monotonic() < deadline:
                        time.sleep(.02)
                    self.assertTrue(server.started, "API server did not start")

                    def fetch(path):
                        with urlopen(f"http://127.0.0.1:{port}{path}", timeout=5) as response:
                            self.assertEqual(response.status, 200)
                            return response.headers, response.read()

                    _, payload = fetch("/api/zones")
                    self.assertEqual(json.loads(payload)[0]["total_clicks"], 3)
                    _, payload = fetch("/api/sessions")
                    self.assertEqual(json.loads(payload)[0]["total_clicks"], 3)
                    _, payload = fetch("/api/trends")
                    self.assertEqual(json.loads(payload)[0]["clicks"], 3)
                    for scope in ("", f"?session_id={sid}"):
                        headers, payload = fetch(f"/api/report.pdf{scope}")
                        self.assertEqual(headers.get_content_type(), "application/pdf")
                        self.assertTrue(payload.startswith(b"%PDF-"))
                        self.assertIn(b"%%EOF", payload[-100:])
                finally:
                    server.should_exit = True
                    worker.join(timeout=5)
                    listener.close()
                    self.assertFalse(worker.is_alive(), "API server did not stop")


if __name__ == "__main__":
    unittest.main(verbosity=2)
