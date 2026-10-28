"""Mouse return gesture tests; no GUI or input hooks are needed."""
from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "overlay"))
from mouse_ai_overlay.navigation import DoubleClickReturn, Hotspots  # noqa: E402


def double_click(navigation, *, x=600, y=400, button="left", start=10.0):
    return [navigation.on_button(x, y, button, pressed, start + elapsed)
            for pressed, elapsed in [(True, 0), (False, .03), (True, .15), (False, .18)]]


class TestHotspots(unittest.TestCase):
    def test_no_target_until_a_click_is_learned(self):
        self.assertIsNone(Hotspots().hottest())

    def test_nearby_clicks_beat_an_isolated_click(self):
        hotspots = Hotspots()
        hotspots.add(100, 100)
        hotspots.add(110, 112)
        hotspots.add(500, 500)
        self.assertEqual(hotspots.hottest(), (105, 106))

    def test_negative_coordinates_on_a_second_monitor(self):
        hotspots = Hotspots()
        hotspots.add(-1810, 700)
        hotspots.add(-1808, 702)
        self.assertEqual(hotspots.hottest(), (-1809, 701))

    def test_equal_counts_keep_the_first_learned_area(self):
        hotspots = Hotspots()
        hotspots.add(100, 100)
        hotspots.add(500, 500)
        self.assertEqual(hotspots.hottest(), (100, 100))

    def test_a_disconnected_screen_cannot_win(self):
        hotspots = Hotspots()
        for _ in range(3):
            hotspots.add(-1810, 700)
        hotspots.add(100, 100)
        self.assertEqual(hotspots.hottest(lambda x, y: x >= 0), (100, 100))
        self.assertIsNone(hotspots.hottest(lambda x, y: False))


class TestDoubleClickReturn(unittest.TestCase):
    def setUp(self):
        self.navigation = DoubleClickReturn()
        for _ in range(3):
            self.navigation.hotspots.add(100, 100)

    def test_only_returns_after_the_second_release(self):
        self.assertEqual(double_click(self.navigation), [None, None, None, (100, 100)])
        self.assertEqual(sum(c.count for c in self.navigation.hotspots.cells.values()), 3)

    def test_gesture_does_not_elect_its_own_location(self):
        navigation = DoubleClickReturn()
        navigation.hotspots.add(100, 100)
        self.assertEqual(double_click(navigation)[-1], (100, 100))
        self.assertEqual(navigation.hotspots.hottest(), (100, 100))

    def test_no_movement_without_existing_history(self):
        navigation = DoubleClickReturn()
        self.assertEqual(double_click(navigation), [None] * 4)
        self.assertIsNone(navigation.hotspots.hottest())

    def test_slow_clicks_do_not_trigger(self):
        navigation = self.navigation
        results = [navigation.on_button(600, 400, "left", pressed, when)
                   for pressed, when in [(True, 10), (False, 10.03),
                                         (True, 10.4), (False, 10.43)]]
        self.assertEqual(results, [None] * 4)
        self.assertEqual(sum(c.count for c in navigation.hotspots.cells.values()), 5)

    def test_fast_clicks_at_different_locations_do_not_trigger(self):
        navigation = self.navigation
        navigation.on_button(600, 400, "left", True, 10)
        navigation.on_button(600, 400, "left", False, 10.03)
        navigation.on_button(630, 400, "left", True, 10.15)
        self.assertIsNone(navigation.on_button(630, 400, "left", False, 10.18))

    def test_right_and_middle_double_clicks_do_not_trigger(self):
        for button in ("right", "middle"):
            with self.subTest(button=button):
                self.assertEqual(double_click(self.navigation, button=button), [None] * 4)

    def test_dragging_the_first_or_second_click_does_not_trigger(self):
        for first_drag in (True, False):
            with self.subTest(first_drag=first_drag):
                navigation = DoubleClickReturn()
                navigation.hotspots.add(100, 100)
                navigation.on_button(600, 400, "left", True, 10)
                navigation.on_button(650 if first_drag else 600, 400, "left", False, 10.03)
                navigation.on_button(600, 400, "left", True, 10.15)
                self.assertIsNone(navigation.on_button(
                    600 if first_drag else 650, 400, "left", False, 10.18))

    def test_holding_the_second_click_does_not_trigger(self):
        navigation = self.navigation
        navigation.on_button(600, 400, "left", True, 10)
        navigation.on_button(600, 400, "left", False, 10.03)
        navigation.on_button(600, 400, "left", True, 10.15)
        self.assertIsNone(navigation.on_button(600, 400, "left", False, 11))

    def test_another_button_cancels_the_gesture(self):
        navigation = self.navigation
        navigation.on_button(600, 400, "left", True, 10)
        navigation.on_button(600, 400, "left", False, 10.03)
        navigation.on_button(600, 400, "left", True, 10.15)
        navigation.on_button(600, 400, "right", True, 10.16)
        self.assertIsNone(navigation.on_button(600, 400, "left", False, 10.18))

    def test_single_clicks_and_release_without_a_press_do_not_move(self):
        navigation = self.navigation
        self.assertIsNone(navigation.on_button(600, 400, "left", False, 9))
        self.assertIsNone(navigation.on_button(600, 400, "left", True, 10))
        self.assertIsNone(navigation.on_button(600, 400, "left", False, 10.03))

    def test_disabling_return_preserves_ordinary_click_learning(self):
        navigation = DoubleClickReturn(enabled=False)
        self.assertEqual(double_click(navigation), [None] * 4)
        self.assertEqual(sum(c.count for c in navigation.hotspots.cells.values()), 2)

    def test_a_new_overlay_session_starts_without_history(self):
        self.assertIsNone(DoubleClickReturn().hotspots.hottest())

    def test_history_survives_long_after_the_visual_glow_fades(self):
        self.assertEqual(double_click(self.navigation, start=10000)[-1], (100, 100))

    def test_a_third_click_does_not_repeat_the_return(self):
        navigation = self.navigation
        self.assertEqual(double_click(navigation)[-1], (100, 100))
        self.assertIsNone(navigation.on_button(600, 400, "left", True, 10.25))
        self.assertIsNone(navigation.on_button(600, 400, "left", False, 10.28))


if __name__ == "__main__":
    unittest.main(verbosity=2)
