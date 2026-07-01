"""Live on-screen heatmap overlay for presentations (Windows).

A transparent, always-on-top, CLICK-THROUGH window spanning the whole
virtual desktop. It paints recent clicks as a fading heatmap over whatever
is on screen, so you can demo interaction live. Press Esc (or Ctrl+C in the
console) to quit.

Run on the Windows host:  python -m mouse_ai_overlay.main

NOTE: for the starter scaffold the overlay runs its own lightweight click
listener so it works standalone. TODO: subscribe to the agent's live stream
(e.g. a loopback UDP socket) so capture happens once and both share it.
"""
from __future__ import annotations

import sys

from PySide6 import QtCore, QtGui, QtWidgets
from pynput import mouse

# The overlay reuses the agent's geometry helper. Add the agent package to
# the path, or install both as editable packages in the same venv.
try:
    from mouse_ai_agent.virtual_desktop import get_virtual_desktop
except ImportError:  # fallback so the file is runnable in isolation
    from dataclasses import dataclass

    @dataclass(frozen=True)
    class _VD:
        x: int = 0
        y: int = 0
        w: int = 1920
        h: int = 1080

    def get_virtual_desktop() -> "_VD":
        return _VD()

from .heatmap import Heatmap


class OverlayWindow(QtWidgets.QWidget):
    # Marshal clicks from the pynput thread onto the Qt thread.
    click_signal = QtCore.Signal(int, int)

    def __init__(self) -> None:
        super().__init__()
        self.vd = get_virtual_desktop()
        self.heatmap = Heatmap()

        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint
            | QtCore.Qt.WindowStaysOnTopHint
            | QtCore.Qt.Tool                       # keep off the taskbar
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        # WA_TransparentForMouseEvents = clicks pass THROUGH to the app below.
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        self.setGeometry(self.vd.x, self.vd.y, self.vd.w, self.vd.h)

        self.click_signal.connect(self._on_click_main_thread)

        # Repaint ~30fps to animate the fade.
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(33)

        self.listener = mouse.Listener(on_click=self._on_click_hook)
        self.listener.start()

    # --- pynput thread ---
    def _on_click_hook(self, x, y, button, pressed):
        if pressed:
            self.click_signal.emit(int(x), int(y))

    # --- Qt thread ---
    @QtCore.Slot(int, int)
    def _on_click_main_thread(self, x: int, y: int) -> None:
        self.heatmap.add(x, y)

    def _tick(self) -> None:
        self.heatmap.prune()
        self.update()

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        if event.key() == QtCore.Qt.Key_Escape:
            QtWidgets.QApplication.quit()

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:
        import time
        now = time.time()
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setPen(QtCore.Qt.NoPen)
        radius = 40
        for p in self.heatmap.points:
            a = p.intensity(now)
            if a <= 0:
                continue
            # Position relative to the window (which starts at the virtual origin).
            cx, cy = p.x - self.vd.x, p.y - self.vd.y
            gradient = QtGui.QRadialGradient(cx, cy, radius)
            gradient.setColorAt(0.0, QtGui.QColor(255, 80, 0, int(200 * a)))
            gradient.setColorAt(1.0, QtGui.QColor(255, 80, 0, 0))
            painter.setBrush(QtGui.QBrush(gradient))
            painter.drawEllipse(QtCore.QPointF(cx, cy), radius, radius)
        painter.end()


def main() -> None:
    app = QtWidgets.QApplication(sys.argv)
    win = OverlayWindow()
    win.showFullScreen()
    print("[mouse-ai] live overlay running. Press Esc to quit.")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
