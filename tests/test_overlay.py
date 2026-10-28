"""Qt rendering regressions for the per-monitor overlay.

Run with the overlay dependencies installed:
    python -m unittest discover -s tests -v

Uses Qt's offscreen backend with two simulated displays. OS input hooks are
mocked, so the tests never capture actual mouse or keyboard events.
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "overlay"))
HAS_OVERLAY_DEPS = all(importlib.util.find_spec(name) is not None
                       for name in ("PySide6", "pynput"))


@unittest.skipUnless(HAS_OVERLAY_DEPS, "Install overlay/requirements.txt for Qt tests")
class TestOverlay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Import pynput's dummy backend; real listeners are replaced below.
        cls.environment = mock.patch.dict(os.environ, {
            "PYNPUT_BACKEND": "dummy", "QT_QPA_OFFSCREEN_NO_GLX": "1",
        })
        cls.environment.start()
        cls.addClassCleanup(cls.environment.stop)
        from mouse_ai_overlay import main as overlay
        cls.overlay = overlay
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        config = Path(cls.temp.name) / "screens.json"
        config.write_text(json.dumps({
            "windowFrameMargins": False,
            "screens": [
                {"name": "primary", "x": 0, "y": 0,
                 "width": 800, "height": 600, "dpr": 1.0},
                {"name": "left", "x": -1200, "y": -300,
                 "width": 1200, "height": 900, "logicalDpi": 144, "dpr": 1.0},
            ],
        }), encoding="utf-8")
        # A Windows drive colon would be parsed as another QPA option. Load
        # the config relative to its temporary directory during app creation.
        previous_directory = Path.cwd()
        try:
            os.chdir(cls.temp.name)
            cls.app = overlay.QtWidgets.QApplication([
                "overlay-tests", "-platform", "offscreen:configfile=screens.json",
            ])
        finally:
            os.chdir(previous_directory)
        cls.app.setQuitOnLastWindowClosed(False)
        cls.screens = {screen.name(): screen for screen in cls.app.screens()}
        if set(cls.screens) != {"primary", "left"}:
            raise unittest.SkipTest("Qt offscreen backend lacks multiple-screen configuration")

    def setUp(self):
        self.mouse_factory = self.enterContext(
            mock.patch.object(self.overlay.mouse, "Listener"))
        self.keyboard_factory = self.enterContext(
            mock.patch.object(self.overlay.keyboard, "Listener"))
        self.cursor_factory = self.enterContext(
            mock.patch.object(self.overlay.mouse, "Controller"))
        self.cursor_factory.return_value.position = None
        self.controller = self.overlay.OverlayController(self.app)
        self.controller.start()
        self.app.processEvents()
        # Control time explicitly in rendering tests rather than run a real timer.
        self.controller.timer.stop()

    def tearDown(self):
        self.controller.stop()
        for window in self.controller.windows.values():
            window.deleteLater()
        self.controller.deleteLater()
        self.app.sendPostedEvents(None, self.overlay.QtCore.QEvent.DeferredDelete)

    def image(self, name, now=1000.0):
        # Exercise the Windows physical-to-logical conversion on any test host.
        with mock.patch.object(self.overlay.sys, "platform", "win32"), \
                mock.patch.object(self.overlay.time, "time", return_value=now):
            return self.controller.windows[self.screens[name]].grab().toImage()

    @staticmethod
    def alpha(image, x, y):
        scale = image.devicePixelRatio()
        return image.pixelColor(round(x * scale), round(y * scale)).alpha()

    def test_two_windows_cover_their_screens_without_accepting_input(self):
        self.assertEqual(len(self.controller.windows), 2)
        Qt = self.overlay.QtCore.Qt
        for screen, window in self.controller.windows.items():
            self.assertEqual(window.geometry(), screen.geometry())
            self.assertIs(window.target_screen, screen)
            self.assertTrue(window.isVisible())
            self.assertFalse(window.isFullScreen())
            self.assertTrue(window.windowFlags() & Qt.WindowTransparentForInput)
            self.assertTrue(window.windowFlags() & Qt.WindowDoesNotAcceptFocus)
            self.assertTrue(window.testAttribute(Qt.WA_TranslucentBackground))
        self.mouse_factory.assert_called_once()
        self.keyboard_factory.assert_called_once()

    def test_clicks_from_both_monitors_are_queued_once_and_render_in_place(self):
        def click_from_hook_thread():
            for x, y in [(-900, 0), (320, 240)]:
                self.controller._on_click_hook(x, y, self.overlay.mouse.Button.left, True)
                self.controller._on_click_hook(x, y, self.overlay.mouse.Button.left, False)

        with mock.patch.object(self.overlay.time, "time", return_value=1000.0):
            worker = threading.Thread(target=click_from_hook_thread)
            worker.start()
            worker.join(timeout=2)
            self.assertFalse(worker.is_alive())
            self.assertEqual(self.controller.heatmap.points, [])
            self.app.processEvents()
        self.assertEqual(len(self.controller.heatmap.points), 2)
        left = self.image("left")
        primary = self.image("primary")
        # (-900, 0) is (300, 300) physical pixels into the 150% left screen.
        self.assertGreater(self.alpha(left, 200, 200), 150)
        self.assertEqual(self.alpha(left, 300, 300), 0)
        self.assertGreater(self.alpha(primary, 320, 240), 150)
        self.assertEqual(self.alpha(primary, 200, 200), 0)

    def test_heat_fades_and_leaves_a_transparent_window(self):
        with mock.patch.object(self.overlay.time, "time", return_value=1000.0):
            self.controller.heatmap.add(-900, 0)
        fresh = self.alpha(self.image("left"), 200, 200)
        faded = self.alpha(self.image("left", now=1001.5), 200, 200)
        self.assertGreater(fresh, faded)
        self.assertGreater(faded, 0)
        with mock.patch.object(self.overlay.time, "time", return_value=1003.1):
            self.controller._tick()
        self.assertEqual(self.controller.heatmap.points, [])
        self.assertEqual(self.alpha(self.image("left", now=1003.1), 200, 200), 0)

    def test_windows_follow_screen_geometry_changes(self):
        screen = self.screens["left"]
        window = self.controller.windows[screen]
        new_geometry = self.overlay.QtCore.QRect(-1000, -200, 700, 500)
        try:
            screen.geometryChanged.emit(new_geometry)
            self.assertEqual(window.geometry(), new_geometry)
        finally:
            screen.geometryChanged.emit(screen.geometry())

    def test_removing_and_reconnecting_a_screen_preserves_shared_heat(self):
        screen = self.screens["left"]
        old_window = self.controller.windows[screen]
        self.controller.heatmap.add(320, 240)
        self.controller._remove_screen(screen)
        self.assertEqual(len(self.controller.windows), 1)
        self.assertFalse(old_window.isVisible())
        self.controller.timer.start(33)
        self.controller._add_screen(screen)
        self.controller.timer.stop()
        replacement = self.controller.windows[screen]
        self.assertIsNot(replacement, old_window)
        self.assertTrue(replacement.isVisible())
        self.assertIs(replacement.heatmap, self.controller.heatmap)
        self.assertEqual(len(replacement.heatmap.points), 1)

    def test_escape_stops_both_windows_and_hooks_without_window_focus(self):
        watchdog = self.overlay.QtCore.QTimer()
        watchdog.setSingleShot(True)
        watchdog.timeout.connect(self.app.quit)
        watchdog.start(2000)
        quit_requests = []
        self.controller.quit_signal.connect(lambda: quit_requests.append(True))
        self.controller._on_key_hook("a")
        self.assertEqual(quit_requests, [])
        self.overlay.QtCore.QTimer.singleShot(
            0, lambda: self.controller._on_key_hook(self.overlay.keyboard.Key.esc))
        try:
            self.app.exec()
        finally:
            watchdog.stop()
        self.assertEqual(quit_requests, [True])
        self.assertTrue(self.controller._stopped)
        self.assertTrue(all(not window.isVisible()
                            for window in self.controller.windows.values()))
        self.mouse_factory.return_value.stop.assert_called_once()
        self.keyboard_factory.return_value.stop.assert_called_once()

    def test_shutdown_is_idempotent(self):
        self.controller.stop()
        self.controller.stop()
        self.assertFalse(self.controller.timer.isActive())
        self.mouse_factory.return_value.stop.assert_called_once()
        self.keyboard_factory.return_value.stop.assert_called_once()

    def prepare_return(self, target=(100, 100)):
        for _ in range(3):
            self.controller.navigation.hotspots.add(*target)
        for pressed, when in [(True, 10), (False, 10.03), (True, 10.15)]:
            self.controller._on_click_main_thread(600, 400, "left", pressed, when)

    def test_return_moves_only_the_pointer_after_the_second_release(self):
        self.prepare_return()
        self.assertFalse(self.controller.jump_timer.isActive())
        self.assertIsNone(self.controller.cursor.position)
        self.controller._on_click_main_thread(600, 400, "left", False, 10.18)
        self.assertTrue(self.controller.jump_timer.isActive())
        self.assertIsNone(self.controller.cursor.position)
        self.controller.jump_timer.stop()
        self.controller._return_to_hotspot()
        self.assertEqual(self.controller.cursor.position, (100, 100))
        self.controller.cursor.click.assert_not_called()
        self.controller.cursor.press.assert_not_called()
        self.controller.cursor.release.assert_not_called()
        self.assertEqual(sum(c.count for c in self.controller.navigation.hotspots.cells.values()), 3)

    def test_a_new_press_cancels_a_pending_return(self):
        self.prepare_return()
        self.controller._on_click_main_thread(600, 400, "left", False, 10.18)
        self.controller._on_click_main_thread(700, 500, "left", True, 10.19)
        self.assertFalse(self.controller.jump_timer.isActive())
        self.controller._return_to_hotspot()
        self.assertIsNone(self.controller.cursor.position)

    def test_return_skips_a_target_on_a_disconnected_monitor(self):
        self.prepare_return(target=(-900, 0))
        self.controller._on_click_main_thread(600, 400, "left", False, 10.18)
        self.controller._remove_screen(self.screens["left"])
        self.controller.jump_timer.stop()
        self.controller._return_to_hotspot()
        self.assertIsNone(self.controller.cursor.position)

    def test_return_uses_physical_bounds_on_a_scaled_monitor(self):
        with mock.patch.object(self.overlay.sys, "platform", "win32"):
            # This is inside the 1200px-wide physical screen, beyond its
            # 800px-wide logical rectangle. It must remain a valid target.
            self.assertTrue(self.controller._on_connected_screen(-100, 500))
            self.prepare_return(target=(-100, 500))
            self.controller._on_click_main_thread(600, 400, "left", False, 10.18)
            self.controller.jump_timer.stop()
            self.controller._return_to_hotspot()
        self.assertEqual(self.controller.cursor.position, (-100, 500))

    def test_shutdown_cancels_a_pending_return(self):
        self.prepare_return()
        self.controller._on_click_main_thread(600, 400, "left", False, 10.18)
        self.controller.stop()
        self.assertFalse(self.controller.jump_timer.isActive())
        self.controller._return_to_hotspot()
        self.assertIsNone(self.controller.cursor.position)


if __name__ == "__main__":
    unittest.main(verbosity=2)
