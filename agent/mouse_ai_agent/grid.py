"""Unified grid mapping over the whole virtual desktop.

A single rows x cols grid is stretched across the combined multi-monitor
desktop (not per-monitor). Each click resolves to exactly one zone id
like 'r0c2' (row 0, col 2).
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Grid:
    rows: int
    cols: int

    def zone_id(self, x_norm: float, y_norm: float) -> str:
        """Map normalized 0..1 coords to a zone id."""
        col = min(self.cols - 1, int(math.floor(x_norm * self.cols)))
        row = min(self.rows - 1, int(math.floor(y_norm * self.rows)))
        col = max(0, col)
        row = max(0, row)
        return f"r{row}c{col}"

    def all_zone_ids(self) -> list[str]:
        return [f"r{r}c{c}" for r in range(self.rows) for c in range(self.cols)]
