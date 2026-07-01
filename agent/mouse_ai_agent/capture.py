"""Desktop-wide click capture via a global mouse hook (pynput).

Records ONLY clicks (button-down), across every monitor, into the local
store. Movement/hover are intentionally not captured.
"""
from __future__ import annotations

import time

from pynput import mouse

from . import store
from .config import Config
from .grid import Grid
from .virtual_desktop import get_virtual_desktop, monitor_at


class ClickCapture:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.grid = Grid(rows=cfg.grid_rows, cols=cfg.grid_cols)
        self.conn = store.connect(cfg.db_path)
        store.init_db(self.conn)
        # Snapshot desktop bounds at session start. If the monitor layout
        # changes mid-session, restart the agent to re-read bounds.
        self.vd = get_virtual_desktop()
        self.session_id = store.start_session(
            self.conn, self.grid.rows, self.grid.cols,
            self.vd.x, self.vd.y, self.vd.w, self.vd.h,
        )
        self._seq = 0
        self._listener: mouse.Listener | None = None

    def _on_click(self, x: int, y: int, button: "mouse.Button", pressed: bool) -> None:
        if not pressed:
            return  # button-down only; ignore the release half of each click
        x_norm, y_norm = self.vd.normalize(x, y)
        zone_id = self.grid.zone_id(x_norm, y_norm)
        self._seq += 1
        store.record_click(
            self.conn,
            session_id=self.session_id,
            seq=self._seq,
            t=time.time(),
            x_virt=x, y_virt=y,
            x_norm=x_norm, y_norm=y_norm,
            button=button.name,
            monitor_id=monitor_at(x, y),
            zone_id=zone_id,
        )

    def run(self) -> None:
        print(f"[mouse-ai] capturing clicks | session={self.session_id[:8]} "
              f"| grid={self.grid.rows}x{self.grid.cols} "
              f"| desktop={self.vd.w}x{self.vd.h}@({self.vd.x},{self.vd.y})")
        print("[mouse-ai] press Ctrl+C to stop.")
        self._listener = mouse.Listener(on_click=self._on_click)
        self._listener.start()
        try:
            self._listener.join()
        finally:
            self.stop()

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
        store.end_session(self.conn, self.session_id)
        self.conn.close()
        print(f"[mouse-ai] session {self.session_id[:8]} ended "
              f"({self._seq} clicks captured).")
