"""Configuration for the capture agent.

Values come from config.json at the repo root (see config.example.json),
with sane defaults so the agent runs out of the box.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

# Repo root = two levels up from this file (agent/mouse_ai_agent/config.py).
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = REPO_ROOT / "config.json"


@dataclass
class Config:
    db_path: str          # where the SQLite store lives (shared with the API)
    grid_rows: int        # unified grid rows over the whole virtual desktop
    grid_cols: int        # unified grid cols

    @staticmethod
    def load(path: Path | None = None) -> "Config":
        path = path or DEFAULT_CONFIG_PATH
        data: dict = {}
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))

        db_path = data.get("db_path") or str(REPO_ROOT / "data" / "mouse_ai.db")
        # Make relative paths resolve against the repo root, not the CWD.
        if not os.path.isabs(db_path):
            db_path = str(REPO_ROOT / db_path)

        grid = data.get("grid", {})
        return Config(
            db_path=db_path,
            grid_rows=int(grid.get("rows", 4)),
            grid_cols=int(grid.get("cols", 4)),
        )
