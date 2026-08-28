#!/usr/bin/env python3
"""Source-tree wrapper for the installed astrology CLI."""
from __future__ import annotations

import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_ROOT))

from astrology.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
