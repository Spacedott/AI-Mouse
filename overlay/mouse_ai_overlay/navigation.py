"""Session click frequency and the double-left-click return gesture.

Coordinates are physical desktop pixels on Windows. This model does not
control the mouse; the Qt controller performs a move after the gesture ends.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

Point = tuple[int, int]
DOUBLE_CLICK_SECONDS = 0.3
DOUBLE_CLICK_DISTANCE = 8
HOTSPOT_SIZE = 64


@dataclass
class _Hotspot:
    count: int = 0
    sum_x: int = 0
    sum_y: int = 0

    @property
    def position(self) -> Point:
        return round(self.sum_x / self.count), round(self.sum_y / self.count)


class Hotspots:
    """Count nearby clicks together; retain counts until the overlay exits."""

    def __init__(self) -> None:
        self.cells: dict[Point, _Hotspot] = {}

    def add(self, x: int, y: int) -> None:
        cell = self.cells.setdefault((x // HOTSPOT_SIZE, y // HOTSPOT_SIZE), _Hotspot())
        cell.count += 1
        cell.sum_x += x
        cell.sum_y += y

    def remove(self, x: int, y: int) -> None:
        """Undo a click that turned out to be part of a return gesture."""
        key = x // HOTSPOT_SIZE, y // HOTSPOT_SIZE
        cell = self.cells[key]
        cell.count -= 1
        cell.sum_x -= x
        cell.sum_y -= y
        if cell.count == 0:
            del self.cells[key]

    def hottest(self, valid: Callable[[int, int], bool] | None = None) -> Point | None:
        cells = (cell for cell in self.cells.values()
                 if valid is None or valid(*cell.position))
        # Dict order breaks equal-count ties in favor of the first learned area.
        best = max(cells, key=lambda cell: cell.count, default=None)
        return best.position if best is not None else None


@dataclass(frozen=True)
class _Press:
    x: int
    y: int
    when: float

    def near(self, x: int, y: int) -> bool:
        return (self.x - x) ** 2 + (self.y - y) ** 2 <= DOUBLE_CLICK_DISTANCE ** 2


class DoubleClickReturn:
    """Recognize a completed fast double-click without counting its two taps."""

    def __init__(self, *, enabled: bool = True,
                 valid_target: Callable[[int, int], bool] | None = None) -> None:
        self.hotspots = Hotspots()
        self.enabled = enabled
        self.valid_target = valid_target
        self.held_buttons: set[str] = set()
        self._first: _Press | None = None
        self._first_released = False
        self._second: _Press | None = None
        self._target: Point | None = None

    def _reset(self) -> None:
        self._first = None
        self._first_released = False
        self._second = None
        self._target = None

    def on_button(self, x: int, y: int, button: str, pressed: bool,
                  when: float) -> Point | None:
        if pressed:
            if button in self.held_buttons:
                return None
            self.held_buttons.add(button)
            target = self.hotspots.hottest(self.valid_target)
            self.hotspots.add(x, y)
            if not self.enabled or button != "left" or len(self.held_buttons) != 1:
                self._reset()
            elif (self._first is not None and self._first_released
                  and 0 <= when - self._first.when <= DOUBLE_CLICK_SECONDS
                  and self._first.near(x, y)):
                self._second = _Press(x, y, when)
            else:
                self._first = _Press(x, y, when)
                self._first_released = False
                self._second = None
                # Snapshot before the first tap so the gesture cannot elect itself.
                self._target = target
            return None

        if button not in self.held_buttons:
            return None
        self.held_buttons.remove(button)
        if button != "left" or self._first is None:
            return None

        if self._second is not None:
            target = None
            if (not self.held_buttons and self._second.near(x, y)
                    and 0 <= when - self._second.when <= DOUBLE_CLICK_SECONDS):
                self.hotspots.remove(self._first.x, self._first.y)
                self.hotspots.remove(self._second.x, self._second.y)
                target = self._target
            self._reset()
            return target

        if (self._first.near(x, y)
                and 0 <= when - self._first.when <= DOUBLE_CLICK_SECONDS):
            self._first_released = True
        else:
            # A held click or drag should not become the start of a gesture.
            self._reset()
        return None
