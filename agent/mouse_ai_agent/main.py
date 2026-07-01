"""Entry point: python -m mouse_ai_agent.main

Run this on the WINDOWS host (not inside WSL) so it can see desktop-wide
mouse events. Launch it manually when you want to record a session.
"""
from __future__ import annotations

from .capture import ClickCapture
from .config import Config


def main() -> None:
    cfg = Config.load()
    ClickCapture(cfg).run()


if __name__ == "__main__":
    main()
