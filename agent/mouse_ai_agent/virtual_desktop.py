"""Virtual-desktop geometry across all monitors (Windows).

Windows treats every monitor as one big "virtual screen" with a single
coordinate space. A monitor placed left of / above the primary produces
NEGATIVE coordinates, so we always normalize against the full virtual
rectangle (origin may be negative).

On non-Windows platforms we fall back to a single-monitor guess so the
agent is still importable/testable; real capture targets Windows.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass

# GetSystemMetrics indices for the virtual screen.
SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79


@dataclass(frozen=True)
class VirtualDesktop:
    x: int   # left edge (may be negative)
    y: int   # top edge (may be negative)
    w: int   # total width across all monitors
    h: int   # total height across all monitors

    def normalize(self, x: int, y: int) -> tuple[float, float]:
        """Map an absolute virtual coord to 0..1 over the whole desktop."""
        nx = (x - self.x) / self.w if self.w else 0.0
        ny = (y - self.y) / self.h if self.h else 0.0
        # Clamp so a click exactly on the far edge stays in-range.
        return _clamp01(nx), _clamp01(ny)


def _clamp01(v: float) -> float:
    return 0.0 if v < 0.0 else (0.999999 if v >= 1.0 else v)


def get_virtual_desktop() -> VirtualDesktop:
    if sys.platform == "win32":
        import ctypes

        gsm = ctypes.windll.user32.GetSystemMetrics
        return VirtualDesktop(
            x=gsm(SM_XVIRTUALSCREEN),
            y=gsm(SM_YVIRTUALSCREEN),
            w=gsm(SM_CXVIRTUALSCREEN),
            h=gsm(SM_CYVIRTUALSCREEN),
        )
    # Fallback for dev on non-Windows: single 1920x1080 origin at (0,0).
    return VirtualDesktop(x=0, y=0, w=1920, h=1080)


def monitor_at(x: int, y: int) -> int | None:
    """Return an index for the monitor containing (x, y), or None if unknown.

    Uses pywin32 when available; recorded only for later per-monitor slicing.
    """
    if sys.platform != "win32":
        return None
    try:
        import win32api  # type: ignore

        for idx, mon in enumerate(win32api.EnumDisplayMonitors()):
            # mon = (hMonitor, hdcMonitor, (left, top, right, bottom))
            left, top, right, bottom = mon[2]
            if left <= x < right and top <= y < bottom:
                return idx
    except Exception:
        return None
    return None
