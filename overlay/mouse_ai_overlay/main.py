"""Live on-screen heatmap overlay for presentations (Windows).

One transparent, always-on-top, click-through window per monitor. All
windows share a fading heatmap and a single global click listener. Press
Esc anywhere (or Ctrl+C in the console) to quit all overlay windows.

Run on the Windows host:  python -m mouse_ai_overlay.main

NOTE: for the starter scaffold the overlay runs its own lightweight click
listener so it works standalone. TODO: subscribe to the agent's live stream
(e.g. a loopback UDP socket) so capture happens once and both share it.
"""
from __future__ import annotations

import argparse
import signal
import sys
import time

from PySide6 import QtCore, QtGui, QtWidgets
from pynput import keyboard, mouse

from .heatmap import Heatmap
from .navigation import DoubleClickReturn


class OverlayWindow(QtWidgets.QWidget):
    """Render the shared heatmap within one screen's bounds."""

    def __init__(self, screen: QtGui.QScreen, heatmap: Heatmap) -> None:
        super().__init__()
        self.target_screen = screen
        self.heatmap = heatmap

        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint
            | QtCore.Qt.WindowStaysOnTopHint
            | QtCore.Qt.Tool  # keep off the taskbar
            | QtCore.Qt.WindowTransparentForInput
            | QtCore.Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self.setScreen(screen)
        self.setGeometry(screen.geometry())
        screen.geometryChanged.connect(self._sync_geometry)

    @QtCore.Slot(QtCore.QRect)
    def _sync_geometry(self, geometry: QtCore.QRect) -> None:
        self.setGeometry(geometry)
        self.update()

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:
        now = time.time()
        geometry = self.target_screen.geometry()
        # pynput reports physical pixels on Windows. Qt keeps each screen's
        # native origin but scales its size, so scale only the local offset.
        # https://doc.qt.io/qt-6/highdpi.html#device-independent-screen-geometry
        scale = self.devicePixelRatioF() if sys.platform == "win32" else 1.0
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setPen(QtCore.Qt.NoPen)
        radius = 40
        for p in self.heatmap.points:
            a = p.intensity(now)
            if a <= 0:
                continue
            cx = (p.x - geometry.x()) / scale
            cy = (p.y - geometry.y()) / scale
            if not (-radius < cx < self.width() + radius
                    and -radius < cy < self.height() + radius):
                continue
            gradient = QtGui.QRadialGradient(cx, cy, radius)
            gradient.setColorAt(0.0, QtGui.QColor(255, 80, 0, int(200 * a)))
            gradient.setColorAt(1.0, QtGui.QColor(255, 80, 0, 0))
            painter.setBrush(QtGui.QBrush(gradient))
            painter.drawEllipse(QtCore.QPointF(cx, cy), radius, radius)
        painter.end()


class OverlayController(QtCore.QObject):
    """Own the windows, shared heatmap, animation timer, and input hooks."""

    click_signal = QtCore.Signal(int, int, str, bool, float)
    quit_signal = QtCore.Signal()

    def __init__(self, app: QtWidgets.QApplication, *, jump_enabled: bool = True) -> None:
        super().__init__(app)
        self.heatmap = Heatmap()
        self.windows: dict[QtGui.QScreen, OverlayWindow] = {}
        self._stopped = False
        self.navigation = DoubleClickReturn(enabled=jump_enabled,
                                            valid_target=self._on_connected_screen)
        self.cursor = mouse.Controller() if jump_enabled else None
        self._jump_target: tuple[int, int] | None = None
        self.jump_timer = QtCore.QTimer(self)
        self.jump_timer.setSingleShot(True)
        self.jump_timer.timeout.connect(self._return_to_hotspot)

        # One timer prunes the shared model and repaints all windows at ~30fps.
        # It also lets Python process Ctrl+C while the Qt event loop is running.
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self._tick)
        for screen in app.screens():
            self._add_screen(screen)
        app.screenAdded.connect(self._add_screen)
        app.screenRemoved.connect(self._remove_screen)
        app.aboutToQuit.connect(self.stop)

        # Marshal hook callbacks onto the Qt thread before touching the model.
        self.click_signal.connect(self._on_click_main_thread,
                                  QtCore.Qt.QueuedConnection)
        self.quit_signal.connect(app.quit, QtCore.Qt.QueuedConnection)
        self.listener = mouse.Listener(on_click=self._on_click_hook)
        self.keyboard_listener = keyboard.Listener(on_press=self._on_key_hook)

    def start(self) -> None:
        for window in self.windows.values():
            # Fullscreen mode may select a different monitor; preserve the
            # screen and exact geometry assigned to each frameless window.
            window.show()
        self.listener.start()
        self.keyboard_listener.start()
        self.timer.start(33)

    @QtCore.Slot(QtGui.QScreen)
    def _add_screen(self, screen: QtGui.QScreen) -> None:
        if self._stopped or screen in self.windows:
            return
        window = OverlayWindow(screen, self.heatmap)
        self.windows[screen] = window
        if self.timer.isActive():
            window.show()

    @QtCore.Slot(QtGui.QScreen)
    def _remove_screen(self, screen: QtGui.QScreen) -> None:
        window = self.windows.pop(screen, None)
        if window is not None:
            screen.geometryChanged.disconnect(window._sync_geometry)
            window.close()
            window.deleteLater()

    def _on_click_hook(self, x, y, button, pressed) -> None:
        # Keep the event's original time even if the Qt thread is busy.
        self.click_signal.emit(int(x), int(y), button.name, bool(pressed), time.monotonic())

    def _on_key_hook(self, key) -> None:
        if key == keyboard.Key.esc:
            self.quit_signal.emit()

    @QtCore.Slot(int, int, str, bool, float)
    def _on_click_main_thread(self, x: int, y: int, button: str,
                              pressed: bool, when: float) -> None:
        if self._stopped:
            return
        if pressed:
            self.heatmap.add(x, y)
            # A new press cancels a pending move rather than moving during a drag.
            self.jump_timer.stop()
            self._jump_target = None
        target = self.navigation.on_button(x, y, button, pressed, when)
        if target is not None:
            self._jump_target = target
            # Let the original button-up reach the app before moving the pointer.
            self.jump_timer.start(20)

    def _on_connected_screen(self, x: int, y: int) -> bool:
        for screen, window in self.windows.items():
            geometry = screen.geometry()
            scale = window.devicePixelRatioF() if sys.platform == "win32" else 1.0
            if (geometry.x() <= x < geometry.x() + geometry.width() * scale
                    and geometry.y() <= y < geometry.y() + geometry.height() * scale):
                return True
        return False

    @QtCore.Slot()
    def _return_to_hotspot(self) -> None:
        target, self._jump_target = self._jump_target, None
        if (self._stopped or target is None or self.cursor is None
                or self.navigation.held_buttons or not self._on_connected_screen(*target)):
            return
        try:
            self.cursor.position = target
        except (OSError, ValueError) as error:
            print(f"[mouse-ai] could not return pointer: {error}", file=sys.stderr)
            return
        # A visual cue only: returning must not add to the learned click counts.
        self.heatmap.add(*target)

    @QtCore.Slot()
    def _tick(self) -> None:
        self.heatmap.prune()
        for window in self.windows.values():
            window.update()

    @QtCore.Slot()
    def stop(self) -> None:
        if self._stopped:
            return
        self._stopped = True
        self.timer.stop()
        self.jump_timer.stop()
        self._jump_target = None
        self.listener.stop()
        self.keyboard_listener.stop()
        for window in self.windows.values():
            window.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Live heatmap across all monitors")
    parser.add_argument("--no-jump", action="store_true",
                        help="show click glows without double-click pointer return")
    options, qt_arguments = parser.parse_known_args()
    app = QtWidgets.QApplication([sys.argv[0], *qt_arguments])
    app.setQuitOnLastWindowClosed(False)
    controller = OverlayController(app, jump_enabled=not options.no_jump)
    previous_sigint = signal.signal(signal.SIGINT, lambda *_: app.quit())
    try:
        controller.start()
        print(f"[mouse-ai] live overlay running on {len(controller.windows)} "
              "monitor(s). Press Esc anywhere or Ctrl+C to quit.")
        if not options.no_jump:
            print("[mouse-ai] fast double left-click returns the pointer to the "
                  "most-clicked area in this overlay session.")
        exit_code = app.exec()
    finally:
        controller.stop()
        signal.signal(signal.SIGINT, previous_sigint)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
