"""Fading-trail heatmap model for the live presentation overlay.

Each click becomes a point that glows then fades over FADE_SECONDS.
Kept independent of the renderer so it can be unit-tested.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

FADE_SECONDS = 3.0     # how long a click stays visible
MAX_POINTS = 500       # cap the buffer so heavy clicking stays smooth


@dataclass
class HeatPoint:
    x: int             # absolute virtual-desktop coord
    y: int
    born: float        # unix seconds when the click happened

    def intensity(self, now: float) -> float:
        """1.0 at birth, linearly to 0.0 at FADE_SECONDS; <=0 means expired."""
        age = now - self.born
        return max(0.0, 1.0 - age / FADE_SECONDS)


@dataclass
class Heatmap:
    points: list[HeatPoint] = field(default_factory=list)

    def add(self, x: int, y: int) -> None:
        self.points.append(HeatPoint(x, y, time.time()))
        if len(self.points) > MAX_POINTS:
            self.points = self.points[-MAX_POINTS:]

    def prune(self, now: float | None = None) -> None:
        now = now if now is not None else time.time()
        self.points = [p for p in self.points if p.intensity(now) > 0.0]
